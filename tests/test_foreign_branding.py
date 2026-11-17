# -*- coding: utf-8 -*-
"""ALVSIA output must never carry a third-party channel or credit line."""
from __future__ import annotations

import sys
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src" / "main" / "python"))

from alvsia_features import (  # noqa: E402
    DEFAULT_BRAND,
    DEFAULT_CHANNEL,
    FOREIGN_BRAND_TOKENS,
    FOREIGN_CHANNEL_TOKENS,
    scrub_foreign_branding,
)

# The exact credit line that shipped inside the imported Zoul.lua payload.
_DEVICE_DUMP_HEADER = "-- Dump By @SRC_HUB / Dev : @XTHrlen"


class ForeignBrandingScrubTests(unittest.TestCase):
    def test_device_dump_header_is_rewritten_to_owner_channel(self):
        cleaned, count = scrub_foreign_branding(_DEVICE_DUMP_HEADER)
        self.assertEqual(count, 2)
        self.assertNotIn("SRC_HUB", cleaned)
        self.assertNotIn("XTHrlen", cleaned)
        self.assertEqual(cleaned, "-- Dump By @ALVSIA_PRO / Dev : @ALVSIA_PRO")

    def test_bare_channel_link_becomes_owner_link(self):
        cleaned, count = scrub_foreign_branding("join t.me/SRC_HUB now")
        self.assertEqual(count, 1)
        self.assertEqual(cleaned, "join https://t.me/ALVSIA_PRO now")

    def test_full_url_is_not_double_prefixed(self):
        cleaned, _ = scrub_foreign_branding("https://t.me/XTHrlen")
        self.assertEqual(cleaned, "https://t.me/ALVSIA_PRO")
        self.assertNotIn("https://https://", cleaned)

    def test_every_declared_token_is_removed(self):
        blob = " ".join(FOREIGN_BRAND_TOKENS + FOREIGN_CHANNEL_TOKENS)
        cleaned, count = scrub_foreign_branding(blob)
        self.assertGreater(count, 0)
        for token in FOREIGN_BRAND_TOKENS:
            self.assertNotIn(token, cleaned, f"brand token survived: {token}")
        for token in FOREIGN_CHANNEL_TOKENS:
            self.assertNotIn(token, cleaned, f"channel token survived: {token}")

    def test_owner_branding_is_used_for_replacements(self):
        cleaned, _ = scrub_foreign_branding("XTHrlen")
        self.assertEqual(DEFAULT_BRAND, "@ALVSIA_PRO")
        self.assertEqual(cleaned, DEFAULT_BRAND)
        self.assertIn(DEFAULT_CHANNEL.split("/")[-1], DEFAULT_CHANNEL)

    def test_clean_text_is_untouched(self):
        text = "local a = 1\nprint(a)\n-- Decompiled by ALVSIA PRO"
        cleaned, count = scrub_foreign_branding(text)
        self.assertEqual(count, 0)
        self.assertEqual(cleaned, text)

    def test_legacy_owner_identity_is_rewritten_in_generated_text(self):
        legacy = "Original" + "OnwerALV"
        legacy_handle = "@" + legacy
        legacy_signature = "Kapten" + " Jack"
        samples = (
            "-- By " + legacy_handle,
            "https://t.me/" + legacy,
            "Credits: " + legacy_signature,
        )
        for sample in samples:
            cleaned, count = scrub_foreign_branding(sample)
            self.assertGreater(count, 0)
            self.assertNotIn(legacy, cleaned)
            self.assertNotIn(legacy_signature, cleaned)
            self.assertIn("ALVSIA", cleaned)

    def test_generated_text_artifacts_are_rebranded_but_inputs_and_binaries_are_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / "OUT" / "SCAN"
            work = root / "WORK"
            out.mkdir(parents=True)
            work.mkdir(parents=True)
            report = out / "result.lua"
            report.write_text("-- By @OriginalOnwerALV\nprint('Kapten Jack')", encoding="utf-8")
            source = work / "original.lua"
            source.write_text("-- By @OriginalOnwerALV", encoding="utf-8")
            binary = out / "asset.so"
            binary.write_bytes(b"\x00Kapten Jack\xff")
            from alvsia_features import scrub_output_text_files
            stats = scrub_output_text_files(root)
            self.assertEqual(stats["files"], 1)
            self.assertIn("@ALVSIA_PRO", report.read_text(encoding="utf-8"))
            self.assertNotIn("OriginalOnwerALV", report.read_text(encoding="utf-8"))
            self.assertIn("OriginalOnwerALV", source.read_text(encoding="utf-8"))
            self.assertEqual(binary.read_bytes(), b"\x00Kapten Jack\xff")

    def test_bridge_scrubs_returned_tool_messages(self):
        bridge = (ROOT / "app" / "src" / "main" / "python" / "alvsia_bridge.py").read_text(encoding="utf-8")
        self.assertIn("scrub_foreign_branding(result)", bridge)
        self.assertIn("scrub_output_text_files(out_root)", bridge)

    def test_legacy_owner_name_is_absent_from_shipped_runtime_source(self):
        legacy = "Original" + "OnwerALV"
        runtime = (ROOT / "app" / "src" / "main" / "python" / "alvsia_ultimate.py").read_text(encoding="utf-8")
        self.assertNotIn(legacy, runtime)

    def test_workspace_readme_uses_current_owner_identity(self):
        work_paths = (ROOT / "app" / "src" / "main" / "java" / "com" / "alvsia" / "pro" / "tool" / "WorkPaths.kt").read_text(encoding="utf-8")
        self.assertIn("ALVSIA PRO 6.0.0", work_paths)
        self.assertIn("Owner: @ALVSIA_PRO", work_paths)
        self.assertNotIn("Original" + "OnwerALV", work_paths)

    def test_empty_input_is_safe(self):
        self.assertEqual(scrub_foreign_branding(""), ("", 0))
        self.assertEqual(scrub_foreign_branding(None), (None, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
