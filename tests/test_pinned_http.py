import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src" / "main" / "python"))
import pinned_http


def tlv(tag, value):
    size = len(value)
    if size < 128:
        length = bytes([size])
    else:
        raw = size.to_bytes((size.bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + length + value


class PinnedHttpTests(unittest.TestCase):
    def test_extracts_spki_der_from_certificate_shape(self):
        version = tlv(0xA0, tlv(0x02, b"\x02"))
        serial = tlv(0x02, b"\x01")
        signature = tlv(0x30, b"")
        issuer = tlv(0x30, b"")
        validity = tlv(0x30, b"")
        subject = tlv(0x30, b"")
        spki = tlv(0x30, tlv(0x02, b"\x01"))
        tbs = tlv(0x30, version + serial + signature + issuer + validity + subject + spki)
        certificate = tlv(0x30, tbs + tlv(0x30, b"") + tlv(0x03, b"\x00"))
        self.assertEqual(pinned_http.extract_spki_der(certificate), spki)

    def test_only_active_unaux_host_is_trusted(self):
        self.assertEqual(pinned_http.PANEL_HOSTS, frozenset(("alvsiapanel.unaux.com",)))

    def test_leaf_and_backup_pins_match_android_vault(self):
        expected = tuple(base64.b64decode(pin) for pin in (
            "3dKRo5uvtVM2x5/NJsOEKFEy803l0rPct3Jv0AoiukE=",
            "xwyjb5aN7tSRWj02XSZa2cKGLxXLdKHUBfLT/7twjhQ=",
            "sLVjNUaFYfW7n6EtgBeEpjOlcnBdNPMrZDRF36iwBdE=",
        ))
        self.assertEqual(pinned_http.PANEL_SPKI_PINS, expected)

    def test_retired_hosts_and_cleartext_are_rejected_before_network(self):
        for url in (
            "http://alvsiapro.cc.cd/api",
            "https://alvsiapro.cc.cd/api",
            "https://api.alvsiapro.cc.cd/api",
            "http://alvsiapanel.unaux.com/api/connect.php",
            "https://example.com/api",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    pinned_http.panel_post(url, json={})


if __name__ == "__main__":
    unittest.main()
