#!/usr/bin/env python3
"""Static contract tests for the ALVSIA seven-layer Security Fabric."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class SecurityFabricTests(unittest.TestCase):
    def test_fabric_has_seven_layers(self):
        src = read("app/src/main/java/com/alvsia/pro/sec/SecurityFabric.kt")
        for layer in (
            "BUILD_TRUST", "ARTIFACT_TRUST", "CHANNEL_TRUST",
            "CRYPTO_TRUST", "CODE_TRUST", "ENVIRONMENT", "RESPONSE"
        ):
            self.assertIn(layer, src)

    def test_fabric_reuses_existing_security_controls(self):
        src = read("app/src/main/java/com/alvsia/pro/sec/SecurityFabric.kt")
        for symbol in (
            "IntegrityBomb.evaluate(ctx)",
            "NetworkGuard.net_guard(ctx)",
            "NativeGuard.isNativeLoaded()",
            "Guard.hostile(ctx)",
            "DualVmGuard.inspect(ctx)",
            "FridaProbe.signals()",
            "RuntimeMappingGuard.signals(ctx)",
        ):
            self.assertIn(symbol, src)

    def test_mapping_guard_limits_detection_to_executable_regions(self):
        src = read("app/src/main/java/com/alvsia/pro/sec/RuntimeMappingGuard.kt")
        self.assertIn("'x' !in fields[1]", src)
        self.assertIn("take(16)", src)
        self.assertIn("/data/local/tmp/", src)

if __name__ == "__main__":
    unittest.main(verbosity=2)
