"""Tests for the offline IL2CPP metadata v39 decoder."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src" / "main" / "python"))

from alvsia_metadata import (  # noqa: E402
    CANONICAL_DESCRIPTOR_ORDER, HEADER_SIZE, MAGIC, VERSION, XOR_KEY,
    decode_metadata_v39_bytes,
)


def make_fixture(bad_first=False):
    count = len(CANONICAL_DESCRIPTOR_ORDER)
    size = HEADER_SIZE + count * 4
    canonical = []
    for index in range(count):
        offset = size + 4 if bad_first and index == 0 else HEADER_SIZE + index * 4
        canonical.append(struct.pack("<III", offset, 4, 1))
    protected = [None] * count
    for canonical_index, protected_index in enumerate(CANONICAL_DESCRIPTOR_ORDER):
        protected[protected_index] = canonical[canonical_index]
    data = bytearray(size)
    struct.pack_into("<II", data, 0, MAGIC, VERSION)
    for index, desc in enumerate(protected):
        start = 8 + index * 12
        data[start:start + 12] = desc
    for offset in range(8, HEADER_SIZE, 4):
        value = struct.unpack_from("<I", data, offset)[0] ^ XOR_KEY
        struct.pack_into("<I", data, offset, value)
    return bytes(data)


class MetadataV39Tests(unittest.TestCase):
    def test_valid_fixture_decodes_and_preserves_payload(self):
        fixture = make_fixture()
        decoded, report = decode_metadata_v39_bytes(fixture)
        self.assertEqual(struct.unpack_from("<II", decoded, 0), (MAGIC, VERSION))
        self.assertEqual(decoded[HEADER_SIZE:], fixture[HEADER_SIZE:])
        self.assertTrue(report["ok"])
        self.assertEqual(report["section_count"], len(CANONICAL_DESCRIPTOR_ORDER))
        self.assertFalse(report["input_modified"])

    def test_rejects_wrong_magic(self):
        fixture = bytearray(make_fixture())
        fixture[0] ^= 0x01
        with self.assertRaisesRegex(ValueError, "magic"):
            decode_metadata_v39_bytes(fixture)

    def test_rejects_wrong_version(self):
        fixture = bytearray(make_fixture())
        struct.pack_into("<I", fixture, 4, 38)
        with self.assertRaisesRegex(ValueError, "version"):
            decode_metadata_v39_bytes(fixture)

    def test_rejects_truncated_header(self):
        with self.assertRaisesRegex(ValueError, "smaller"):
            decode_metadata_v39_bytes(b"\x00" * (HEADER_SIZE - 1))

    def test_rejects_out_of_range_section(self):
        with self.assertRaisesRegex(ValueError, "descriptor"):
            decode_metadata_v39_bytes(make_fixture(bad_first=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
