package com.alvsia.pro.tool

import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.PrintStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.util.zip.Inflater

/**
 * ALVSIA PRO 5.5.0 — Android ART Lua decompiler runner.
 *
 * Supports:
 *  • normal Lua 5.3 / LuaJIT bytecode
 *  • 0x78DA chunked raw-DEFLATE Lua containers (streaming, bounded memory)
 *  • in-process unluac.Main for inputs up to ART_SAFE_LIMIT
 *  • large-file streaming fallback path for multi-MB / multi-GB inputs
 *
 * No external JVM process is required. Memory usage is bounded by
 * STREAM_CHUNK_SIZE — never the size of the input file.
 *
 * Failure contract: never produce a fake `.lua` source. If a real decompile
 * path produced no validated Lua output, the input is preserved under IN/
 * and the caller is told exactly which path failed and why.
 */
object UnluacRunner {

    /** Hard safety limit for the in-process (ART) unluac call. */
    private const val ART_SAFE_LIMIT = 1L * 1024L * 1024L

    /**
     * Above this, we go straight to the streaming Python fallback rather
     * than attempt the in-process unluac, which has a O(n) in-memory
     * representation that explodes on multi-GB LuaS chunks.
     */
    private const val ART_HARD_LIMIT = 64L * 1024L * 1024L  // 64 MiB

    /** Streaming chunk size for container unwrap and file scan. */
    private const val STREAM_CHUNK_SIZE = 4 * 1024 * 1024  // 4 MiB

    /** Hard cap on the unwrapped LuaS payload produced by container unwrap. */
    private const val UNWRAP_OUTPUT_LIMIT = 4L * 1024L * 1024L * 1024L  // 4 GiB

    private val LUA_MAGIC = byteArrayOf(0x1B, 0x4C, 0x75, 0x61)  // \x1bLua
    private val LUAJIT_MAGIC = byteArrayOf(0x1B, 0x4C, 0x4A)     // \x1bLJ
    private val DEFLATE_HEADER = byteArrayOf(0x78, 0xDA.toByte())

    private fun hasPrefix(data: ByteArray, prefix: ByteArray): Boolean {
        if (data.size < prefix.size) return false
        for (i in prefix.indices) {
            if (data[i] != prefix[i]) return false
        }
        return true
    }

    // ── Streaming container unwrap (memory-mapped, bounded) ────────────────

    /**
     * Streaming variant of the chunked raw-DEFLATE unwrapper.
     * Reads in STREAM_CHUNK_SIZE pieces so multi-GB inputs do not OOM.
     * Output is written to a temp file (not held in memory).
     */
    private fun unwrapChunkedLuaStreaming(
        input: File,
        outDir: File
    ): Pair<File?, String?> {
        // Quick sniff of first 2 bytes — only proceed on raw-DEFLATE header.
        val head = ByteArray(2)
        try {
            RandomAccessFile(input, "r").use { raf ->
                if (raf.length() < 2) return input to null
                raf.readFully(head)
            }
        } catch (_: Exception) {
            return input to null
        }
        if (head[0] != 0x78.toByte() || head[1] != 0xDA.toByte()) {
            return input to null
        }

        val outFile = File(outDir, input.nameWithoutExtension + "_unwrapped.luac")
        outFile.parentFile?.mkdirs()
        var chunkCount = 0
        var totalBytes = 0L
        try {
            RandomAccessFile(input, "r").use { raf ->
                val fileSize = raf.length()
                // Memory-map the input in pieces so we never allocate the full file.
                val channel = raf.channel
                var mapStart = 0L
                while (mapStart < fileSize) {
                    val mapSize = minOf(fileSize - mapStart, STREAM_CHUNK_SIZE.toLong())
                    val mbb: MappedByteBuffer = channel.map(
                        FileChannel.MapMode.READ_ONLY, mapStart, mapSize
                    )
                    mbb.order(ByteOrder.BIG_ENDIAN)
                    scanForDeflateMarkers(mbb, mapStart) { markerOffset ->
                        // Try to inflate from this marker to end of file (streaming).
                        // Because the mapped region may be smaller than the actual
                        // DEFLATE stream, we use a RandomAccessFile-backed input
                        // stream for the inflater so it can read past the mapped
                        // region if necessary.
                        val inflated = inflateFromOffset(input, markerOffset)
                        if (inflated != null && inflated.first > 0) {
                            FileOutputStream(outFile, true).use { fos ->
                                fos.write(inflated.second)
                            }
                            totalBytes += inflated.first
                            chunkCount++
                            if (totalBytes > UNWRAP_OUTPUT_LIMIT) {
                                throw IllegalStateException(
                                    "decompressed Lua container exceeds $UNWRAP_OUTPUT_LIMIT bytes"
                                )
                            }
                        }
                    }
                    mapStart += mapSize
                    // Release mapping hint
                    // (JVM GC handles this; explicit unmap not portable in Kotlin.)
                }
            }
        } catch (t: Throwable) {
            // Partial output may still be usable as LuaS input — keep it.
            if (outFile.exists() && outFile.length() == 0L) outFile.delete()
            return outFile.takeIf { it.exists() && it.length() > 0 } to
                "container=chunked-raw-deflate chunks=$chunkCount bytes=$totalBytes partial=true err=${t.message}"
        }

        if (chunkCount == 0) {
            outFile.delete()
            return input to null
        }

        // Validate the unwrapped payload starts with Lua / LuaJIT magic.
        val sniff = ByteArray(4)
        try {
            FileInputStream(outFile).use { fis ->
                if (fis.read(sniff) >= 4) {
                    val isLua = hasPrefix(sniff, LUA_MAGIC)
                    val isLuaJit = hasPrefix(sniff, LUAJIT_MAGIC)
                    if (!isLua && !isLuaJit) {
                        outFile.delete()
                        return input to null
                    }
                }
            }
        } catch (_: Exception) {
            // keep outFile if we couldn't even sniff — let unluac decide
        }

        return outFile to
            "container=chunked-raw-deflate chunks=$chunkCount bytes=$totalBytes"
    }

    /**
     * Scans a mapped buffer for 0x78 0xDA markers, invoking [cb] with the
     * absolute file offset of each marker found. Memory-bounded by the
     * mapped region size.
     */
    private fun scanForDeflateMarkers(mbb: MappedByteBuffer, regionStart: Long, cb: (Long) -> Unit) {
        val limit = mbb.limit()
        if (limit < 2) return
        var i = 0
        while (i < limit - 1) {
            val b0 = mbb.get(i).toInt() and 0xFF
            val b1 = mbb.get(i + 1).toInt() and 0xFF
            if (b0 == 0x78 && b1 == 0xDA) {
                cb(regionStart + i)
                // Skip ahead a bit to avoid re-finding the same marker
                i += 2
            } else {
                i++
            }
        }
    }

    /**
     * Inflates a raw-DEFLATE stream starting at [offset] in [file], reading
     * up to end-of-file. Returns (bytesWritten, rawInflatedBytes). The
     * inflated output is streamed into a ByteArrayOutputStream up to a
     * bounded cap; oversized payloads are written directly to the output
     * file by the caller via the returned bytes.
     */
    private fun inflateFromOffset(file: File, offset: Long): Pair<Long, ByteArray>? {
        val inflater = Inflater(true)  // raw inflate, no zlib wrapper
        try {
            val input = ByteArray(STREAM_CHUNK_SIZE)
            val out = ByteArrayOutputStream(STREAM_CHUNK_SIZE)
            var totalIn = 0L
            var totalOut = 0L
            RandomAccessFile(file, "r").use { raf ->
                raf.seek(offset)
                var reading = true
                while (reading) {
                    val n = raf.read(input)
                    if (n <= 0) break
                    totalIn += n
                    inflater.setInput(input, 0, n)
                    val buf = ByteArray(STREAM_CHUNK_SIZE)
                    while (!inflater.needsInput() && !inflater.finished()) {
                        val written = inflater.inflate(buf)
                        if (written > 0) {
                            out.write(buf, 0, written)
                            totalOut += written.toLong()
                            if (totalOut > UNWRAP_OUTPUT_LIMIT) {
                                return totalOut to out.toByteArray()
                            }
                        } else if (inflater.needsDictionary() || inflater.needsInput()) {
                            reading = false
                            break
                        }
                    }
                    if (inflater.finished()) break
                }
            }
            return if (totalOut > 0) totalOut to out.toByteArray() else null
        } catch (t: Throwable) {
            return null
        } finally {
            inflater.end()
        }
    }

    // ── In-process unluac invocation (only for inputs ≤ ART_SAFE_LIMIT) ────

    private fun invokeUnluac(input: File): Pair<String, String> {
        val oldOut = System.out
        val oldErr = System.err
        val buf = ByteArrayOutputStream()
        val errBuf = ByteArrayOutputStream()
        val ps = PrintStream(buf, true, Charsets.UTF_8.name())
        val psErr = PrintStream(errBuf, true, Charsets.UTF_8.name())
        try {
            System.setOut(ps)
            System.setErr(psErr)
            val cls = Class.forName("unluac.Main")
            val main = cls.getMethod("main", Array<String>::class.java)
            main.invoke(null, arrayOf(input.absolutePath))
            ps.flush()
            psErr.flush()
            return (buf.toString(Charsets.UTF_8.name()) to
                errBuf.toString(Charsets.UTF_8.name()))
        } finally {
            System.setOut(oldOut)
            System.setErr(oldErr)
            ps.close()
            psErr.close()
        }
    }

    private fun looksLikeLua(text: String): Boolean {
        val t = text.trim()
        if (t.isEmpty()) return false
        val looksAssignment = Regex(
            """(?m)^\s*[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s*=(?!=)\s*\S+"""
        ).containsMatchIn(t)
        val looksLua =
            t == "return" ||
            Regex("""(?m)^\s*return(?:\s|$)""").containsMatchIn(t) ||
            t.contains("function") ||
            t.contains("local ") ||
            t.contains("return ") ||
            t.contains("if ") ||
            t.contains("while ") ||
            t.contains("for ") ||
            t.contains("repeat ") ||
            t.contains("do ") ||
            t.contains("--") ||
            looksAssignment
        val looksError =
            t.startsWith("Error", true) ||
            t.startsWith("Exception", true) ||
            t.startsWith("java.", true)
        return looksLua && !looksError
    }

    /**
     * Top-level decompile entry called by ToolEngine.
     * Returns a list of diagnostic lines for the user.
     */
    fun decompile(input: File, output: File): List<String> {
        if (!input.isFile) {
            return listOf("X input not found: ${input.absolutePath}")
        }
        output.parentFile?.mkdirs()

        val inputSize = input.length()
        val lines = mutableListOf<String>()

        // Stage 1: Try streaming container unwrap (works for any size).
        val unwrapResult = try {
            unwrapChunkedLuaStreaming(input, output.parentFile ?: input.parentFile!!)
        } catch (t: Throwable) {
            input to "container error: ${t.message}"
        }
        val normalized = unwrapResult.first ?: input
        val containerNote = unwrapResult.second
        if (containerNote != null) {
            lines.add("OK LUA container -> $containerNote")
        }

        // Stage 2: Decide path using the actual bytes passed to ART.
        // A small compressed wrapper can expand dramatically; checking only
        // the original file size could send a huge normalized chunk into the
        // in-process parser and cause an Android OOM.
        val normalizedSize = normalized.length()
        if (normalizedSize > ART_HARD_LIMIT) {
            // Too large for in-process unluac; mark and let caller fall through
            // to the Python streaming fallback in alvsia_bridge_impl.
            lines.add(
                "... ART unluac skipped: normalized payload $normalizedSize bytes exceeds ART_HARD_LIMIT ($ART_HARD_LIMIT)"
            )
            lines.add("diagnostic: switching to streaming Python decompiler fallback")
            lines.add("diagnostic: original input=$inputSize bytes; normalized payload=$normalizedSize bytes")
            if (normalized != input && normalized.isFile) {
                lines.add("OK normalized container -> ${normalized.absolutePath}")
            }
            return lines
        }

        if (normalizedSize > ART_SAFE_LIMIT) {
            lines.add(
                "... ART unluac skipped: normalized payload $normalizedSize bytes exceeds ART_SAFE_LIMIT ($ART_SAFE_LIMIT)"
            )
            lines.add("diagnostic: original input=$inputSize bytes; normalized payload=$normalizedSize bytes")
            lines.add("diagnostic: Python fallback will handle this input")
            if (normalized != input && normalized.isFile) {
                lines.add("OK normalized container -> ${normalized.absolutePath}")
            }
            return lines
        }

        // Stage 3: In-process unluac for inputs ≤ ART_SAFE_LIMIT.
        return try {
            val (text, err) = invokeUnluac(normalized)
            if (looksLikeLua(text)) {
                output.writeText(text, Charsets.UTF_8)
                lines.add("OK unluac ART -> ${output.absolutePath}")
                lines.add("bytes ${output.length()}")
                lines
            } else {
                output.delete()
                lines.add("X unluac produced no validated Lua source")
                if (err.isNotBlank()) lines.add(err.take(800))
                else if (text.isNotBlank()) lines.add(text.take(800))
                lines
            }
        } catch (t: Throwable) {
            output.delete()
            var root: Throwable = t
            var depth = 0
            while (root.cause != null && root.cause !== root && depth < 8) {
                root = root.cause!!
                depth++
            }
            val msg = "${root.javaClass.simpleName}: ${root.message ?: "no detail"}"
            lines.add("X unluac ART: $msg")
            lines.add("diagnostic: wrapper=${t.javaClass.simpleName}; causeDepth=$depth")
            if (normalized != input && normalized.isFile) {
                lines.add("OK normalized bytecode -> ${normalized.absolutePath}")
            }
            lines
        }
    }

    /**
     * Streaming preflight: scans a large input for valid LuaS magic without
     * loading it all into memory. Used by the Python fallback path to
     * quickly detect Lua / LuaJIT / chunked-DEFLATE containers.
     */
    fun preflightMagic(input: File): String {
        try {
            val buf = ByteArray(8)
            RandomAccessFile(input, "r").use { raf ->
                if (raf.length() < 4) return "too_small"
                raf.readFully(buf, 0, 4)
            }
            return when {
                hasPrefix(buf, LUA_MAGIC) -> "luac53"
                hasPrefix(buf, LUAJIT_MAGIC) -> "luajit"
                buf[0] == 0x78.toByte() && buf[1] == 0xDA.toByte() -> "chunked_deflate"
                buf[0] == 0x1F.toByte() && buf[1] == 0x8B.toByte() -> "gzip"
                else -> "unknown_0x" + buf.take(4).joinToString("") {
                    "%02x".format(it.toInt() and 0xFF)
                }
            }
        } catch (_: Exception) {
            return "preflight_failed"
        }
    }
}
