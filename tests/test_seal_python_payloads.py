import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tools.seal_python import BUILD_ID, CERT_HEX, MAGIC, MODULES, _seed, seal_payload


class ProductionSealPayloadTests(unittest.TestCase):
    def setUp(self):
        self.seed = bytes(range(32))
        self.cert = bytes.fromhex(CERT_HEX)
        self.build_id = BUILD_ID

    def test_production_envelope_matches_native_layout(self):
        plain = b"print('ALVISIA')"
        payload = seal_payload(plain, self.seed, self.cert, self.build_id)
        self.assertEqual(payload[:8], MAGIC)
        self.assertEqual(len(payload), 8 + 12 + len(plain) + 16)
        nonce = payload[8:20]
        self.assertEqual(AESGCM(__import__("hashlib").sha256(
            self.seed + self.cert + self.build_id.encode("utf-8")
        ).digest()).decrypt(nonce, payload[20:], MAGIC), plain)

    def test_tampering_is_detected(self):
        payload = bytearray(seal_payload(b"source", self.seed, self.cert, self.build_id))
        payload[-1] ^= 1
        key = __import__("hashlib").sha256(
            self.seed + self.cert + self.build_id.encode("utf-8")
        ).digest()
        with self.assertRaises(InvalidTag):
            AESGCM(key).decrypt(bytes(payload[8:20]), bytes(payload[20:]), MAGIC)

    def test_nonce_is_random(self):
        first = seal_payload(b"same source", self.seed, self.cert, self.build_id)
        second = seal_payload(b"same source", self.seed, self.cert, self.build_id)
        self.assertNotEqual(first, second)

    def test_invalid_seed_fails_closed(self):
        with patch.dict(os.environ, {"ALVSIA_SEAL_SEED_HEX": "invalid"}):
            with self.assertRaises(SystemExit):
                _seed()

    def test_module_manifest_is_nonempty_and_unique(self):
        self.assertEqual(len(MODULES), 27, "release sealing inventory must include all 27 reviewed modules")
        self.assertIn("alvsia_metadata.py", MODULES)
        self.assertEqual(len(MODULES), len(set(MODULES)))
        self.assertTrue(all((ROOT / "app/src/main/python" / rel).is_file() for rel in MODULES))
        loader = (ROOT / "app/src/main/python" / "sealed_loader.py").read_text(encoding="utf-8")
        audit = (ROOT / "tools/audit_release_apk.py").read_text(encoding="utf-8")
        for rel in MODULES:
            module = rel[:-3].replace("/", ".")
            blob = rel[:-3].replace("/", "_") + ".alv"
            self.assertIn(f'"{module}": "{blob}"', loader, f"loader missing {module}")
            self.assertIn(f'"{blob}"', audit, f"APK audit missing {blob}")

    def test_t24_lua_module_is_sealed_and_mapped(self):
        rel = "lua_engine/t24.py"
        self.assertIn(rel, MODULES)
        loader = (ROOT / "app/src/main/python" / "sealed_loader.py").read_text(encoding="utf-8")
        self.assertIn('"lua_engine.t24": "lua_engine_t24.alv"', loader)

    def test_lua_orchestrator_module_is_sealed_and_mapped(self):
        rel = "lua_engine/orchestrator.py"
        self.assertIn(rel, MODULES)
        loader = (ROOT / "app/src/main/python" / "sealed_loader.py").read_text(encoding="utf-8")
        audit = (ROOT / "tools/audit_release_apk.py").read_text(encoding="utf-8")
        self.assertIn('"lua_engine.orchestrator": "lua_engine_orchestrator.alv"', loader)
        self.assertIn('"lua_engine_orchestrator.alv"', audit)

    def test_smart_lua_protection_modules_are_sealed_and_mapped(self):
        loader = (ROOT / "app/src/main/python/sealed_loader.py").read_text(encoding="utf-8")
        for rel, module, blob in (
            ("lua_engine/protection.py", "lua_engine.protection", "lua_engine_protection.alv"),
            ("lua_engine/protection_pipeline.py", "lua_engine.protection_pipeline", "lua_engine_protection_pipeline.alv"),
        ):
            self.assertIn(rel, MODULES)
            self.assertIn(f'"{module}": "{blob}"', loader)

    def test_large_lua_streaming_module_is_sealed_and_mapped(self):
        rel = "lua_engine/streaming_decompiler.py"
        self.assertIn(rel, MODULES)
        loader = (ROOT / "app/src/main/python" / "sealed_loader.py").read_text(encoding="utf-8")
        self.assertIn('"lua_engine.streaming_decompiler": "lua_engine_streaming_decompiler.alv"', loader)


if __name__ == "__main__":
    unittest.main()
