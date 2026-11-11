"""Runtime regression tests for ALVSIA PRIVATE TOOL engine primitives."""
import sys
import unittest
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"
sys.path.insert(0, str(PYTHON_DIR))

import alvsia_private as private


class PrivateToolEngineTests(unittest.TestCase):
    def test_all_dispatch_dependencies_exist(self):
        for name in (
            "ZUCCipher", "AESKeyScanner", "XORKeyRecovery",
            "LuaBytecodeParser", "LuaOpcodeConverter", "CompressionBestFit",
            "APKAuditor", "StringConstantRecovery", "EntropyAnalyzer",
            "PAKManifestGenerator", "AlvsiaLuaWriter",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(private, name), name)

    def test_zuc128_zero_key_zero_iv_known_answer(self):
        # ZUC-128 standard all-zero test vector begins 27bede74018082da.
        cipher = private.ZUCCipher(bytes(16), bytes(16))
        self.assertEqual(cipher.encrypt(bytes(8)).hex(), "27bede74018082da")

    def test_zuc_rejects_wrong_key_or_iv_length(self):
        with self.assertRaises(ValueError):
            private.ZUCCipher(b"short", bytes(16))
        with self.assertRaises(ValueError):
            private.ZUCCipher(bytes(16), b"short")

    def test_aes_scanner_detects_sbox(self):
        hits = private.AESKeyScanner.scan(private._AES_SBOX)
        self.assertTrue(any(hit["type"] == "sbox_table" for hit in hits))

    def test_entropy_map_handles_empty_and_uniform_data(self):
        self.assertEqual(private.EntropyAnalyzer.block_entropy(b""), 0.0)
        self.assertEqual(private.EntropyAnalyzer.block_entropy(bytes(256)), 0.0)

    def test_compression_best_fit_round_trip(self):
        source = (b"ALVSIA-private-engine-test-" * 100)
        result = private.CompressionBestFit.compress(source, method="zlib")
        self.assertEqual(__import__("zlib").decompress(result), source)


    def test_zuc_encrypt_decrypt_round_trip_with_fresh_instances(self):
        key = bytes(range(16))
        iv = bytes(range(16, 32))
        plaintext = b"ALVSIA ZUC regression payload"
        ciphertext = private.ZUCCipher(key, iv).encrypt(plaintext)
        recovered = private.ZUCCipher(key, iv).decrypt(ciphertext)
        self.assertEqual(recovered, plaintext)

    def test_xor_recovery_returns_empty_for_short_input(self):
        self.assertEqual(private.XORKeyRecovery.recover(b"too short"), [])

    def test_entropy_analyze_reports_offsets_and_bounds(self):
        data = bytes(64) + bytes(range(256))
        blocks = private.EntropyAnalyzer.analyze(data, block_size=64)
        self.assertEqual([offset for offset, _ in blocks], [0, 64, 128, 192, 256])
        self.assertTrue(all(0.0 <= entropy <= 8.0 for _, entropy in blocks))
        self.assertEqual(blocks[0][1], 0.0)

    def test_apk_auditor_reports_zip_structure(self):
        import tempfile
        import zipfile
        with tempfile.TemporaryDirectory() as td:
            apk = Path(td) / "sample.apk"
            with zipfile.ZipFile(apk, "w") as zf:
                zf.writestr("AndroidManifest.xml", b"binary-manifest-placeholder")
                zf.writestr("classes.dex", b"dex\n035\x00")
                zf.writestr("lib/arm64-v8a/libsample.so", b"\x7fELF")
            report = private.APKAuditor.audit(str(apk))
            self.assertTrue(report["manifest_present"])
            self.assertEqual(report["dex_count"], 1)
            self.assertEqual(report["native_arches"], ["arm64-v8a"])
            self.assertEqual(report["total_files"], 3)


    def test_lua53_parser_consumes_dumped_strings_and_integer_constants(self):
        # Minimal standard Lua 5.3 chunk with one string and one integer constant.
        header = (
            b"\x1bLua\x53\x00\x19\x93\r\n\x1a\n"
            b"\x04\x08\x04\x08\x08"
            b"\x78\x56\x00\x00\x00\x00\x00\x00"
            + __import__("struct").pack("<d", 370.5)
        )
        proto = (
            b"\x03@x\x00"                 # source string (size includes NUL)
            + (0).to_bytes(4, "little")   # line defined
            + (0).to_bytes(4, "little")   # last line
            + b"\x00\x00\x02"             # params, vararg, max stack
            + (0).to_bytes(4, "little")   # code count
            + (3).to_bytes(4, "little")   # constant count
            + b"\x04\x06hello\x00"         # string constant
            + b"\x13" + (123456789).to_bytes(8, "little", signed=True)
            + b"\x13" + (-42).to_bytes(8, "little", signed=True)
            + (0).to_bytes(4, "little")   # upvalues
            + (0).to_bytes(4, "little")   # child protos
            + (0).to_bytes(4, "little") * 3  # debug table counts
        )
        info = private.LuaBytecodeParser(header + proto).parse()
        self.assertEqual(info.source_name, "@x")
        self.assertEqual([item.value for item in info.strings], ["hello"])
        self.assertEqual([item.value for item in info.numbers], [123456789, -42])


    def test_lua51_parser_reads_header_upvalue_count_and_constants(self):
        # Minimal little-endian Lua 5.1 chunk with one string and one double constant.
        header = b"\x1bLua\x51\x00\x01\x04\x08\x04\x08\x00"
        proto = (
            b"\x00"                         # nups (Lua 5.1 only)
            + (3).to_bytes(8, "little") + b"@x\x00"  # source string
            + (0).to_bytes(4, "little")     # line defined
            + (0).to_bytes(4, "little")     # last line
            + b"\x00\x00\x02"               # params, vararg, max stack
            + (0).to_bytes(4, "little")     # code count
            + (2).to_bytes(4, "little")     # constant count
            + b"\x04" + (6).to_bytes(8, "little") + b"hello\x00"
            + b"\x03" + __import__("struct").pack("<d", 12.5)
            + (0).to_bytes(4, "little")     # child protos
            + (0).to_bytes(4, "little")     # lineinfo
            + (0).to_bytes(4, "little")     # locvars
            + (0).to_bytes(4, "little")     # upvalue names
        )
        info = private.LuaBytecodeParser(header + proto).parse()
        self.assertEqual(info.source_name, "@x")
        self.assertEqual([item.value for item in info.strings], ["hello"])
        self.assertEqual([item.value for item in info.numbers], [12.5]
)

    def test_bgmi_and_heping_structured_lua_conversion(self):
        import struct
        from lua_engine.decompiler53 import load_chunk
        keys = {
            "bgmi": private.ALVSIA_BGMI_XOR_KEY,
            "heping": private.ALVSIA_HEPING_XOR_KEY,
        }
        header = (
            b"\x1bLua\x53\x00\x19\x93\r\n\x1a\n"
            + bytes((4, 4, 4, 8, 8))
            + struct.pack("<q", 0x5678)
            + struct.pack("<d", 370.5)
        )
        self.assertEqual(len(header), 33)
        for variant, key in keys.items():
            with self.subTest(variant=variant):
                def encrypted_string(value):
                    raw = value.encode("utf-8")
                    enc = bytes(byte ^ key[i % len(key)] for i, byte in enumerate(raw))
                    return bytes((len(enc) + 1,)) + enc
                # Minimal game-variant Lua 5.3 Proto: one RETURN instruction, one string constant.
                proto = bytearray()
                proto.extend(encrypted_string("@fixture"))
                proto.extend(struct.pack("<ii", 0, 0))
                proto.extend(bytes((0, 0, 2)))
                proto.extend(struct.pack("<I", 2))
                proto.extend(struct.pack("<II", 0, 38))
                proto.extend(struct.pack("<I", 1))
                proto.append(4)
                proto.extend(encrypted_string("hello"))
                proto.extend(struct.pack("<I", 0))  # upvalues
                proto.extend(struct.pack("<I", 0))  # nested protos
                proto.extend(struct.pack("<I", 0))  # compressed lineinfo
                proto.extend(struct.pack("<I", 0))  # abslineinfo
                proto.extend(struct.pack("<I", 0))  # local variables
                proto.extend(struct.pack("<I", 0))  # upvalue names
                source_variant = header + b"\x00" + bytes(proto)
                converted = private.LuaOpcodeConverter(variant=variant).convert_bytes(source_variant)
                parsed = load_chunk(converted)
                self.assertEqual(parsed.source, "@fixture")
                self.assertEqual(parsed.constants, ["hello"])
                self.assertEqual([ins & 0x3F for ins in parsed.code],
                                 [13, 38] if variant == "bgmi" else [30, 38])

    def test_lua53_instruction_format_table_matches_vm_layout(self):
        formats = private._STD_FMT
        self.assertEqual(len(formats), 47)
        self.assertEqual(formats[30], 2)   # JMP: iAsBx
        self.assertEqual(formats[38], 0)   # RETURN: iABC
        self.assertEqual(formats[39], 2)   # FORLOOP: iAsBx
        self.assertEqual(formats[40], 2)   # FORPREP: iAsBx
        self.assertEqual(formats[41], 0)   # TFORCALL: iABC
        self.assertEqual(formats[42], 2)   # TFORLOOP: iAsBx
        self.assertEqual(formats[43], 0)   # SETLIST: iABC
        self.assertEqual(formats[44], 1)   # CLOSURE: iABx
        self.assertEqual(formats[45], 0)   # VARARG: iABC
        self.assertEqual(formats[46], 3)   # EXTRAARG: iAx
    def test_lua_variant_converter_rejects_corrupt_counts(self):
        import struct
        header = (
            b"\x1bLua\x53\x00\x19\x93\r\n\x1a\n"
            + bytes((4, 4, 4, 8, 8))
            + struct.pack("<q", 0x5678)
            + struct.pack("<d", 370.5)
        )
        raw = header + b"\x00" + bytes((1,)) + b"@" + bytes(8) + bytes((0, 0, 2)) + struct.pack("<I", 0x58E44AA5)
        with self.assertRaisesRegex(ValueError, "instruction count"):
            private.LuaOpcodeConverter("bgmi").convert_bytes(raw)

    def test_lua_parser_rejects_non_lua_magic(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            private.LuaBytecodeParser(b"not a lua file").parse()


    def test_compression_best_level_selects_a_fit(self):
        source = b"ALVSIA-compression-budget-" * 100
        level, size = private.CompressionBestFit.best_level_for_target(
            source, target_size=128, method="zlib"
        )
        self.assertGreaterEqual(level, 1)
        self.assertLessEqual(level, 9)
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 128)
        compressed = __import__("zlib").compress(source, level)
        self.assertEqual(len(compressed), size)
        self.assertEqual(__import__("zlib").decompress(compressed), source)

    def test_compression_best_level_reports_impossible_budget(self):
        level, size = private.CompressionBestFit.best_level_for_target(
            b"not compressible enough", target_size=1, method="zlib"
        )
        self.assertEqual((level, size), (-1, 0))

    def test_compression_best_level_rejects_unknown_method(self):
        with self.assertRaisesRegex(ValueError, "Unknown method"):
            private.CompressionBestFit.best_level_for_target(b"data", 32, "invalid")

    def test_compression_target_budget_is_respected(self):
        source = b"A" * 4096
        compressed = private.CompressionBestFit.compress(source, method="zlib", target_size=128)
        self.assertIsNotNone(compressed)
        self.assertLessEqual(len(compressed), 128)
        self.assertEqual(__import__("zlib").decompress(compressed), source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
