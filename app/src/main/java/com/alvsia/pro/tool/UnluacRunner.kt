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

    private data class InflatedMember(val bytesWritten: Long, val endOffset: Long)

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
        // Never append a new run to a stale output from an earlier attempt.
        try { outFile.delete() } catch (_: Exception) { }
        var chunkCount = 0
        var totalBytes = 0L
        try {
            RandomAccessFile(input, "r").use { raf ->
                val fileSize = raf.length()
                val channel = raf.channel
                var mapStart = 0L
                // Ignore marker-like bytes inside a member already decoded;
                // the inflater's exact end offset is more reliable than
                // searching compressed payload bytes for another 0x78DA.
                var skipMarkersBefore = 0L
                while (mapStart < fileSize) {
                    val mapSize = minOf(fileSize - mapStart, STREAM_CHUNK_SIZE.toLong())
                    // Include one look-ahead byte so a 0x78DA marker split
                    // across two mapping windows is not silently missed.
                    val mapLength = minOf(
                        fileSize - mapStart,
                        mapSize + if (mapStart + mapSize < fileSize) 1L else 0L
                    )
                    val mbb: MappedByteBuffer = channel.map(
                        FileChannel.MapMode.READ_ONLY, mapStart, mapLength
                    )
                    scanForDeflateMarkers(mbb, mapStart) { markerOffset ->
                        if (markerOffset < skipMarkersBefore) return@scanForDeflateMarkers
                        val remaining = UNWRAP_OUTPUT_LIMIT - totalBytes
                        if (remaining <= 0L) {
                            throw IllegalStateException(
                                "decompressed Lua container exceeds $UNWRAP_OUTPUT_LIMIT bytes"
                            )
                        }
                        val partFile = File(outDir, "${outFile.name}.$markerOffset.part")
                        try {
                            val member = inflateFromOffset(input, markerOffset, partFile, remaining)
                            if (member != null && member.bytesWritten > 0L) {
                                FileOutputStream(outFile, true).use { fos ->
                                    FileInputStream(partFile).use { fis ->
                                        fis.copyTo(fos, STREAM_CHUNK_SIZE)
                                    }
                                    fos.fd.sync()
                                }
                                totalBytes += member.bytesWritten
                                chunkCount++
                                skipMarkersBefore = member.endOffset
                            }
                        } finally {
                            try { partFile.delete() } catch (_: Exception) { }
                        }
                    }
                    mapStart += mapSize
                }
            }
        } catch (_: Throwable) {
            // Never pass a truncated multi-member payload to a decompiler.
            // Keep the original input intact so the Python normalizer can
            // retry with its EOF-aware stream parser and emit diagnostics.
            try { outFile.delete() } catch (_: Exception) { }
            return input to null
        }

        if (chunkCount == 0) {
            outFile.delete()
            return input to null
        }

        val sniff = ByteArray(4)
        try {
            if (outFile.length() < sniff.size.toLong()) {
                outFile.delete()
                return input to null
            }
            RandomAccessFile(outFile, "r").use { raf -> raf.readFully(sniff) }
            val isLua = hasPrefix(sniff, LUA_MAGIC)
            val isLuaJit = hasPrefix(sniff, LUAJIT_MAGIC)
            if (!isLua && !isLuaJit) {
                outFile.delete()
                return input to null
            }
        } catch (_: Exception) {
            try { outFile.delete() } catch (_: Exception) { }
            return input to null
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
     * Inflate one raw-DEFLATE member to a temporary file. Memory stays
     * bounded to two fixed-size buffers regardless of decompressed size.
     * A candidate is accepted only when the inflater reaches its end marker.
     */
    private fun inflateFromOffset(
        file: File,
        offset: Long,
        output: File,
        maxOutputBytes: Long
    ): InflatedMember? {
        val inflater = Inflater(true)
        var totalOut = 0L
        var finished = false
        var memberEndOffset = -1L
        try {
            val inputBuffer = ByteArray(STREAM_CHUNK_SIZE)
            val outputBuffer = ByteArray(STREAM_CHUNK_SIZE)
            RandomAccessFile(file, "r").use { raf ->
                // The marker is the two-byte zlib-style 0x78DA tag;
                // this payload is raw DEFLATE, so the inflater must start
                // immediately after those marker bytes.
                raf.seek(offset + 2L)
                FileOutputStream(output, false).use { out ->
                    while (!inflater.finished()) {
                        if (inflater.needsInput()) {
                            val count = raf.read(inputBuffer)
                            if (count <= 0) break
                            inflater.setInput(inputBuffer, 0, count)
                        }
                        val written = inflater.inflate(outputBuffer)
                        if (written > 0) {
                            totalOut += written.toLong()
                            if (totalOut > maxOutputBytes) {
                                throw IllegalStateException(
                                    "inflated member exceeds remaining output limit $maxOutputBytes"
                                )
                            }
                            out.write(outputBuffer, 0, written)
                        } else if (inflater.needsDictionary()) {
                            break
                        } else if (!inflater.needsInput() && !inflater.finished()) {
                            break
                        }
                    }
                    out.flush()
                    out.fd.sync()
                    finished = inflater.finished()
                    if (finished) {
                        // getRemaining() is the unconsumed tail of the last
                        // input buffer; subtract it from the file position to
                        // find the exact end of this DEFLATE member.
                        memberEndOffset = raf.filePointer - inflater.remaining.toLong()
                    }
                }
            }
            return if (finished && totalOut > 0L && memberEndOffset > offset) {
                InflatedMember(totalOut, memberEndOffset)
            } else null
        } catch (_: Throwable) {
            return null
        } finally {
            inflater.end()
            if (!finished || totalOut == 0L) {
                try { output.delete() } catch (_: Exception) { }
            }
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
