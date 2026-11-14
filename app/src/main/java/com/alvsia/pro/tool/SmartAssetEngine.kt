package com.alvsia.pro.tool

import java.io.File
import java.security.MessageDigest
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.min

/** Safe, generic asset/binary intelligence. No server secrets or game credentials. */
object SmartAssetEngine {
    private const val MAX_BYTES = 512L * 1024L * 1024L
    private const val MAX_PATCHES = 10000

    fun run(subId: String, inputPath: String, taskId: String): List<String> {
        val out = WorkPaths.taskModuleOut(taskId, 20).also { it.mkdirs() }
        val f = File(inputPath)
        if (!f.isFile) return listOf("X SMART ASSET ENGINE requires a regular input file")
        if (f.length() > MAX_BYTES) return listOf("X Asset analysis limit exceeded: 512 MiB")
        return try {
            when (subId) {
                "asset_smart" -> smart(f, out, taskId)
                "asset_fingerprint" -> fingerprint(f, out)
                "asset_scan_ids" -> scanIds(f, out)
                "asset_context" -> context(f, out)
                "asset_patch" -> patch(f, out)
                "asset_validate" -> validate(f, out)
                else -> listOf("X Unsupported Smart Asset operation: " + subId)
            }
        } catch (t: Throwable) {
            listOf("X Smart Asset Engine failed: " + t.javaClass.simpleName + ": " + (t.message ?: "no detail"))
        }
    }

    private fun smart(f: File, out: File, taskId: String): List<String> {
        val lines = mutableListOf<String>()
        lines.add("OK Smart Asset pipeline started")
        lines.addAll(fingerprint(f, out))
        lines.addAll(scanIds(f, out))
        lines.addAll(context(f, out))

        val config = File(WorkPaths.taskRoot(taskId), "WORK/asset_patch_map.txt")
        val patchRequested = config.isFile && config.length() > 0L
        if (patchRequested) {
            val patchLines = patch(f, out, taskId)
            lines.addAll(patchLines)
            val patched = File(out, f.name + ".asset_patched")
            lines.addAll(validate(
                if (patchLines.any { it.startsWith("OK safe asset patch:") } && patched.isFile) patched else f,
                out
            ))
        } else {
            lines.add("NOTE no asset mapping supplied; modification skipped (read-only analysis)")
            lines.addAll(validate(f, out))
        }
        return lines
    }

    private fun fingerprint(f: File, out: File): List<String> {
        val b = f.readBytes()
        val hints = mutableListOf<String>()
        if (b.size >= 4 && b[0] == 0x9e.toByte() && b[1] == 0x2a.toByte() && b[2] == 0x83.toByte() && b[3] == 0xc1.toByte()) hints += "UE_ASSET_MAGIC_CANDIDATE"
        if (b.containsSeq("UAsset".toByteArray())) hints += "UASSET_MARKER"
        if (b.containsSeq("UEXP".toByteArray())) hints += "UEXP_MARKER"
        if (b.containsSeq("\u001bLua".toByteArray())) hints += "LUA_MARKER"
        if (b.size >= 4 && ByteBuffer.wrap(b, 0, 4).order(ByteOrder.LITTLE_ENDIAN).int == 0x04034b50) hints += "ZIP_CANDIDATE"
        val sha = sha256(b)
        val report = File(out, f.name + ".asset_fingerprint.json")
        report.writeText(
            "{\n" +
            "  \"file\":\"" + json(f.name) + "\",\n" +
            "  \"size\":" + f.length() + ",\n" +
            "  \"sha256\":\"" + sha + "\",\n" +
            "  \"entropy\":" + entropy(b) + ",\n" +
            "  \"ascii_ratio\":" + asciiRatio(b) + ",\n" +
            "  \"hints\":[" + hints.joinToString(",") { "\"" + json(it) + "\"" } + "]\n" +
            "}\n"
        )
        return listOf("OK asset fingerprint generated", "SHA-256 " + sha, "OK OUTPUT -> " + report.absolutePath)
    }

    private fun scanIds(f: File, out: File): List<String> {
        val text = f.readBytes().toString(Charsets.ISO_8859_1)
        val re = Regex("[A-Za-z0-9_./:-]{6,96}")
        val hits = LinkedHashSet<String>()
        re.findAll(text).forEach { m -> if (looksLikeAssetId(m.value)) hits += m.value; if (hits.size >= 5000) return@forEach }
        val report = File(out, f.name + ".asset_ids.txt")
        report.writeText(hits.joinToString("\n") + if (hits.isNotEmpty()) "\n" else "")
        return listOf("OK asset ID scan: " + hits.size + " candidates", "OK OUTPUT -> " + report.absolutePath)
    }

    private fun context(f: File, out: File): List<String> {
        val b = f.readBytes()
        val patterns = listOf("Skin","Outfit","Weapon","Hit","Loot","Crate","Theme","Atmosphere","Size","Texture","Material","Mesh","UAsset","UEXP")
        val report = File(out, f.name + ".asset_context.jsonl")
        var hits = 0
        report.bufferedWriter().use { w ->
            for (p in patterns) {
                val needle = p.toByteArray()
                var pos = 0
                while (true) {
                    val at = indexOf(b, needle, pos)
                    if (at < 0) break
                    val lo = maxOf(0, at - 48)
                    val hi = min(b.size, at + needle.size + 96)
                    val ctx = json(b.copyOfRange(lo, hi).toString(Charsets.ISO_8859_1))
                    w.appendLine("{\"pattern\":\"" + json(p) + "\",\"offset\":" + at + ",\"context\":\"" + ctx + "\"}")
                    hits++
                    pos = at + needle.size
                    if (hits >= 10000) break
                }
                if (hits >= 10000) break
            }
        }
        return listOf("OK asset contextual scan: " + hits + " matches", "OK OUTPUT -> " + report.absolutePath)
    }

    private fun patch(f: File, out: File, taskId: String): List<String> {
        val cfg = File(WorkPaths.taskRoot(taskId), "WORK/asset_patch_map.txt")
        if (!cfg.isFile) return listOf("X Missing WORK/asset_patch_map.txt", "hint: old_hex=new_hex; both must have equal byte length")
        var b = f.readBytes()
        var applied = 0
        cfg.readLines().filter { it.isNotBlank() && !it.trimStart().startsWith("#") }.take(MAX_PATCHES).forEach { line ->
            val p = line.split("=", limit = 2)
            if (p.size != 2) return@forEach
            val old = parseHex(p[0]) ?: return@forEach
            val new = parseHex(p[1]) ?: return@forEach
            if (old.isEmpty() || old.size != new.size) return@forEach
            var pos = 0
            while (pos <= b.size - old.size && applied < MAX_PATCHES) {
                val at = indexOf(b, old, pos)
                if (at < 0) break
                System.arraycopy(new, 0, b, at, new.size)
                applied++
                pos = at + new.size
            }
        }
        if (applied == 0) return listOf("X No safe same-length asset mappings matched the input")
        val target = File(out, f.name + ".asset_patched")
        if (target.canonicalPath == f.canonicalPath) return listOf("X Refusing to overwrite source asset")
        target.writeBytes(b)
        val before = sha256(f.readBytes())
        val after = sha256(b)
        val report = File(out, f.name + ".asset_patch_report.json")
        report.writeText("{\"source_sha256\":\"" + before + "\",\"output_sha256\":\"" + after + "\",\"applied\":" + applied + ",\"source_unchanged\":true}")
        return listOf("OK safe asset patch: " + applied + " replacements", "SHA-256 before " + before, "SHA-256 after  " + after, "OK OUTPUT -> " + target.absolutePath)
    }

    private fun validate(f: File, out: File): List<String> {
        val b = f.readBytes()
        val sha = sha256(b)
        val issues = mutableListOf<String>()
        if (b.isEmpty()) issues += "empty_file"
        val report = File(out, f.name + ".asset_validate.json")
        report.writeText("{\"file\":\"" + json(f.name) + "\",\"size\":" + f.length() + ",\"sha256\":\"" + sha + "\",\"issues\":[" + issues.joinToString(",") { "\"" + it + "\"" } + "],\"source_modified\":false}")
        return listOf("OK asset validation completed", "issues=" + issues.size, "SHA-256 " + sha, "OK OUTPUT -> " + report.absolutePath)
    }

    private fun parseHex(s: String): ByteArray? = try {
        val x = s.trim().removePrefix("0x").replace(" ", "")
        if (x.isEmpty() || x.length % 2 != 0 || !x.matches(Regex("[0-9A-Fa-f]+"))) null
        else ByteArray(x.length / 2) { x.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    } catch (_: Exception) { null }

    private fun indexOf(h: ByteArray, n: ByteArray, from: Int): Int {
        if (n.isEmpty() || h.size < n.size) return -1
        outer@ for (i in from..h.size - n.size) {
            for (j in n.indices) if (h[i + j] != n[j]) continue@outer
            return i
        }
        return -1
    }

    private fun ByteArray.containsSeq(n: ByteArray): Boolean = indexOf(this, n, 0) >= 0
    private fun looksLikeAssetId(s: String) = listOf("asset","skin","outfit","texture","material","weapon","crate","hit","theme").any { s.contains(it, true) }
    private fun asciiRatio(b: ByteArray) = if (b.isEmpty()) 0.0 else b.count { it in 32..126 || it == 9.toByte() || it == 10.toByte() }.toDouble() / b.size
    private fun entropy(b: ByteArray): Double {
        if (b.isEmpty()) return 0.0
        val c = IntArray(256); b.forEach { c[it.toInt() and 255]++ }
        var e = 0.0
        c.filter { it > 0 }.forEach { n -> val p = n.toDouble() / b.size; e -= p * kotlin.math.log(p, 2.0) }
        return e
    }
    private fun sha256(b: ByteArray) = MessageDigest.getInstance("SHA-256").digest(b).joinToString("") { "%02x".format(it) }
    private fun json(s: String) = s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")
}
