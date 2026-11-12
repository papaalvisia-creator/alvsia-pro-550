package com.alvsia.pro.asset

import android.content.Context
import com.alvsia.pro.sec.NativeGuard
import java.io.File
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

object AssetVault {
    private val MAGIC = byteArrayOf(0x41, 0x4C, 0x56, 0x53, 0x41, 0x31, 0x00)

    // Asset index entries are untrusted until validated; keep all names as single path segments.
    private fun isSafeAssetName(name: String): Boolean =
        name.isNotBlank() &&
            name != "." && name != ".." &&
            '\u0000' !in name &&
            '/' !in name && '\\' !in name

    private fun isSafeAssetPath(path: String): Boolean =
        path.isNotBlank() &&
            !path.startsWith("/") &&
            !path.contains("..") &&
            '\u0000' !in path &&
            '\\' !in path &&
            path.split('/').all { it.isNotBlank() && it != "." }

    private fun safeJarTarget(root: File, name: String): File? {
        if (!isSafeAssetName(name) || !name.endsWith(".jar")) return null
        return try {
            val canonicalRoot = root.canonicalFile
            val target = File(canonicalRoot, name).canonicalFile
            if (target.parentFile == canonicalRoot && target.name == name) target else null
        } catch (_: Exception) {
            null
        }
    }

    private fun openBlob(blob: ByteArray, key: ByteArray): ByteArray? {
        return try {
            if (blob.size < 7 + 12 + 16) return null
            if (!blob.copyOfRange(0, 7).contentEquals(MAGIC)) return null
            val nonce = blob.copyOfRange(7, 19)
            val ct = blob.copyOfRange(19, blob.size)
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
            c.doFinal(ct)
        } catch (_: Exception) {
            null
        }
    }

    private fun loadXopSealedMap(ctx: Context): Map<String, ByteArray>? {
        return try {
            // XopProtector injects ProtectorAssets only into the protected APK.
            // Reflection keeps normal/debug builds independent of the injected shell.
            val clazz = Class.forName("com.yqsh.protector.shell.ProtectorAssets")
            val readBytes = clazz.getMethod("readBytes", Context::class.java, String::class.java)
            val index = (readBytes.invoke(null, ctx, "nx/i.dat") as ByteArray)
                .toString(Charsets.UTF_8)
            val out = mutableMapOf<String, ByteArray>()
            for (line in index.lines()) {
                val parts = line.split("=", limit = 2)
                if (parts.size != 2) continue
                val logical = parts[0].trim()
                val file = parts[1].trim()
                if (logical.isEmpty() || !isSafeAssetName(file)) continue
                val plain = readBytes.invoke(null, ctx, "nx/$file") as ByteArray
                out[logical] = plain
            }
            out
        } catch (_: Throwable) {
            null
        }
    }

    /**
     * Read an ordinary bundled asset through Xop ProtectorAssets when present.
     * Debug/unprotected APKs retain the Android AssetManager fallback.
     */
    fun readAssetBytes(ctx: Context, assetPath: String): ByteArray? {
        if (!isSafeAssetPath(assetPath)) return null
        val protectorAssets = try {
            Class.forName("com.yqsh.protector.shell.ProtectorAssets")
        } catch (_: Throwable) {
            null
        }
        if (protectorAssets != null) {
            // Protected APK: fail closed if PAS1 decryption fails; never fall back to plaintext.
            return try {
                val readBytes = protectorAssets.getMethod("readBytes", Context::class.java, String::class.java)
                readBytes.invoke(null, ctx, assetPath) as? ByteArray
            } catch (_: Throwable) {
                null
            }
        }
        // Debug/unprotected APK: the original asset is intentionally plaintext.
        return try {
            ctx.assets.open(assetPath).use { it.readBytes() }
        } catch (_: Throwable) {
            null
        }
    }

    fun loadSealedMap(ctx: Context): Map<String, ByteArray> {
        // Final Xop APK: assets/nx/* is PAS1 encrypted and must be read through
        // ProtectorAssets. Keep the existing ALVSA1 path as a compatibility fallback
        // for debug/validation builds before Xop packaging.
        loadXopSealedMap(ctx)?.let { return it }

        val k = NativeGuard.assetSealKey() ?: return emptyMap()
        val out = mutableMapOf<String, ByteArray>()
        return try {
            val am = ctx.assets
            val idxBlob = am.open("nx/i.dat").use { it.readBytes() }
            val idx = openBlob(idxBlob, k)?.toString(Charsets.UTF_8) ?: return emptyMap()
            for (line in idx.lines()) {
                val parts = line.split("=", limit = 2)
                if (parts.size != 2) continue
                val logical = parts[0].trim()
                val file = parts[1].trim()
                if (logical.isEmpty() || !isSafeAssetName(file)) continue
                val blob = am.open("nx/$file").use { it.readBytes() }
                val plain = openBlob(blob, k) ?: continue
                out[logical] = plain
            }
            out
        } catch (_: Exception) {
            emptyMap()
        } finally {
            k.fill(0)
        }
    }

    fun materializeJars(ctx: Context, jarsDir: File): Int {
        jarsDir.mkdirs()
        var n = 0
        for ((name, bytes) in loadSealedMap(ctx)) {
            val dest = safeJarTarget(jarsDir, name) ?: continue
            // Length alone is not integrity: an attacker could alter a JAR without changing its size.
            val alreadyValid = try {
                dest.isFile && dest.length() == bytes.size.toLong() &&
                    dest.readBytes().contentEquals(bytes)
            } catch (_: Exception) {
                false
            }
            if (alreadyValid) {
                n++
                continue
            }
            try {
                dest.writeBytes(bytes)
            } catch (_: Exception) {
                continue
            } finally {
                // Do not keep decrypted JAR plaintext resident after materialization.
                bytes.fill(0)
            }
            try {
                dest.setReadable(true, true)
                dest.setWritable(true, true)
            } catch (_: Exception) {
            }
            n++
        }
        return n
    }
}
