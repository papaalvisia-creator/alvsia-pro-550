package com.alvsia.pro.tool

import android.content.Context
import android.net.Uri
import java.io.FileInputStream
import java.io.RandomAccessFile

/**
 * ALVSIA PRO 5.5.2 — FileMagic (UX Sprint 1)
 *
 * Auto-detects file type from magic bytes (first 8 bytes).
 * Returns a suggested subtool ID + human-readable description.
 *
 * Used by ToolWorkspace when user picks a file — shows a banner:
 *   "Detected: Lua 5.3 bytecode. Suggested: Smart Decompile"
 */
object FileMagic {

    enum class FileType {
        LUA_53_BYTECODE,
        LUAJIT_BYTECODE,
        LUA_SOURCE,
        CHUNKED_DEFLATE,
        GZIP,
        ZIP_OBB,
        ELF_SO,
        ELF_EXECUTABLE,
        APK,
        PAK_TENCENT,
        ALVLUA1_PROTECTED,
        ALVSEAL3_PROTECTED,
        PLAIN_TEXT,
        UNKNOWN
    }

    data class DetectionResult(
        val type: FileType,
        val label: String,
        val suggestedSubtool: String?,  // subtool ID or null
        val suggestedModule: Int,       // module ID (1-18)
        val sizeBytes: Long,
        val isLargeFile: Boolean       // > 8 MiB
    )

    /**
     * Detect file type from first 8 bytes.
     * Does not load the whole file into memory — reads only the header.
     */
    fun detect(ctx: Context, uri: Uri): DetectionResult {
        val header = ByteArray(16)
        var fileSize = 0L
        try {
            ctx.contentResolver.openInputStream(uri)?.use { ins ->
                var offset = 0
                while (offset < header.size) {
                    val count = ins.read(header, offset, header.size - offset)
                    if (count < 0) break
                    if (count == 0) continue
                    offset += count
                }
                if (offset < 4) return unknown(fileSize)
            } ?: return unknown(fileSize)
            // Try to get file size from cursor
            ctx.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val sizeIdx = cursor.getColumnIndex(android.provider.OpenableColumns.SIZE)
                if (sizeIdx >= 0 && cursor.moveToFirst()) {
                    fileSize = cursor.getLong(sizeIdx)
                }
            }
        } catch (_: Exception) {
            return unknown(0)
        }

        val isLarge = fileSize > 8L * 1024 * 1024

        // Some exporters prepend a Lua comment/shebang banner before bytecode.
        // Mirror the Python preflight conservatively: accept only text-comment lines.
        val embeddedLua = detectCommentPrefixedLua(ctx, uri)
        if (embeddedLua != null) {
            val label = if (embeddedLua == "luajit") "LuaJIT" else "Lua 5.3"
            return DetectionResult(
                if (embeddedLua == "luajit") FileType.LUAJIT_BYTECODE else FileType.LUA_53_BYTECODE,
                "$label bytecode (comment-prefixed)",
                "lua_decompile", 5, fileSize, isLarge
            )
        }

        // Check magic bytes
        val result = when {
            // Lua 5.3 bytecode: 1b 4c 75 61 53
            header[0] == 0x1B.toByte() && header[1] == 0x4C.toByte() &&
                header[2] == 0x75.toByte() && header[3] == 0x61.toByte() &&
                header[4] == 0x53.toByte() -> {
                if (isLarge) {
                    DetectionResult(FileType.LUA_53_BYTECODE, "Lua 5.3 bytecode (${fileSize} bytes — streaming)",
                        "lua_decompile", 5, fileSize, true)
                } else {
                    DetectionResult(FileType.LUA_53_BYTECODE, "Lua 5.3 bytecode",
                        "lua_decompile", 5, fileSize, false)
                }
            }

            // LuaJIT bytecode: 1b 4c 4a
            header[0] == 0x1B.toByte() && header[1] == 0x4C.toByte() &&
                header[2] == 0x4A.toByte() ->
                DetectionResult(FileType.LUAJIT_BYTECODE, "LuaJIT bytecode",
                    "lua_decompile", 5, fileSize, false)

            // ALVLUA1 protected (our own AES-256-GCM format)
            header.size >= 7 &&
                header[0] == 0x41.toByte() && header[1] == 0x4C.toByte() &&
                header[2] == 0x56.toByte() && header[3] == 0x4C.toByte() &&
                header[4] == 0x55.toByte() && header[5] == 0x41.toByte() &&
                header[6] == 0x31.toByte() ->
                DetectionResult(FileType.ALVLUA1_PROTECTED, "ALVLUA1 protected payload",
                    "lua_protect_decrypt", 18, fileSize, false)

            // ALVSEAL3 protected (our own VM protect format) — check text header
            fileSize > 200 && detectTextHeader(ctx, uri, "-- ALVSIA PRO 5.5.0 VM-protected") ->
                DetectionResult(FileType.ALVSEAL3_PROTECTED, "ALVSEAL3 VM-protected Lua",
                    "lua_vm_deobfuscate", 5, fileSize, false)

            // Chunked DEFLATE: 78 DA
            header[0] == 0x78.toByte() && header[1] == 0xDA.toByte() ->
                DetectionResult(FileType.CHUNKED_DEFLATE, "Chunked DEFLATE container",
                    "lua_decompile", 5, fileSize, false)

            // GZIP: 1F 8B
            header[0] == 0x1F.toByte() && header[1] == 0x8B.toByte() ->
                DetectionResult(FileType.GZIP, "GZIP compressed",
                    "lua_decompile", 5, fileSize, false)

            // ZIP/OBB: 50 4B 03 04
            header[0] == 0x50.toByte() && header[1] == 0x4B.toByte() &&
                header[2] == 0x03.toByte() && header[3] == 0x04.toByte() ->
                DetectionResult(FileType.ZIP_OBB, "ZIP/OBB archive",
                    "obb_unzip", 4, fileSize, false)

            // ELF: 7F 45 4C 46
            header[0] == 0x7F.toByte() && header[1] == 0x45.toByte() &&
                header[2] == 0x4C.toByte() && header[3] == 0x46.toByte() ->
                DetectionResult(FileType.ELF_SO, "ELF shared library (.so)",
                    "so_xor_scan", 10, fileSize, false)

            // APK: PK + .apk extension (check last path segment)
            uri.lastPathSegment?.endsWith(".apk") == true ->
                DetectionResult(FileType.APK, "Android APK",
                    "audit_apk", 17, fileSize, false)

            // PAK (Tencent): check for version bytes in trailer — too complex for header check
            // Fall through to plain text or unknown

            // Plain text (printable ASCII first 4 chars)
            header[0] in 32..126 && header[1] in 32..126 &&
                header[2] in 32..126 && header[3] in 32..126 ->
                DetectionResult(FileType.PLAIN_TEXT, "Text/Source file",
                    null, 0, fileSize, false)

            else -> unknown(fileSize)
        }

        return result
    }

    private fun detectCommentPrefixedLua(ctx: Context, uri: Uri): String? {
        return try {
            val head = ByteArray(64 * 1024)
            var length = 0
            ctx.contentResolver.openInputStream(uri)?.use { ins ->
                while (length < head.size) {
                    val count = ins.read(head, length, head.size - length)
                    if (count < 0) break
                    if (count == 0) continue
                    length += count
                }
            } ?: return null

            val bytes = head.copyOf(length)
            val candidates = listOf(
                Triple(byteArrayOf(0x1B, 0x4C, 0x75, 0x61), "luac", 4),
                Triple(byteArrayOf(0x1B, 0x4C, 0x4A), "luajit", 3)
            )
            for ((magic, kind, markerLength) in candidates) {
                val offset = bytes.indexOfSequence(magic)
                if (offset <= 0 || offset + markerLength >= bytes.size) continue
                val prefix = try {
                    Charsets.UTF_8.newDecoder()
                        .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                        .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
                        .decode(java.nio.ByteBuffer.wrap(bytes, 0, offset)).toString()
                } catch (_: Exception) {
                    continue
                }
                val lines = prefix.split(Regex("\\r?\\n"))
                if (lines.isNotEmpty() && lines.all {
                    it.isBlank() || it.trimStart().startsWith("--") || it.trimStart().startsWith("#!")
                } && prefix.none { it.code < 32 && it !in "\\t\\r\\n" }) {
                    return kind
                }
            }
            null
        } catch (_: Exception) {
            null
        }
    }

    private fun ByteArray.indexOfSequence(sequence: ByteArray): Int {
        if (sequence.isEmpty() || size < sequence.size) return -1
        for (start in 0..(size - sequence.size)) {
            var matched = true
            for (i in sequence.indices) {
                if (this[start + i] != sequence[i]) {
                    matched = false
                    break
                }
            }
            if (matched) return start
        }
        return -1
    }

    private fun detectTextHeader(ctx: Context, uri: Uri, marker: String): Boolean {
        return try {
            ctx.contentResolver.openInputStream(uri)?.use { ins ->
                val buf = ByteArray(256)
                val read = ins.read(buf)
                if (read > 0) {
                    val text = String(buf, 0, read, Charsets.UTF_8)
                    marker in text
                } else false
            } ?: false
        } catch (_: Exception) {
            false
        }
    }

    private fun unknown(size: Long): DetectionResult {
        return DetectionResult(
            type = FileType.UNKNOWN,
            label = "Unknown format (0x${size.toString(16)})",
            suggestedSubtool = null,
            suggestedModule = 0,
            sizeBytes = size,
            isLargeFile = size > 8L * 1024 * 1024
        )
    }
}
