# -*- coding: utf-8 -*-
"""ALVSIA output must never carry a third-party channel or credit line."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"))

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
        self.assertEqual(cleaned, DEFAULT_BRAND)
        self.assertIn(DEFAULT_CHANNEL.split("/")[-1], DEFAULT_CHANNEL)

    def test_clean_text_is_untouched(self):
        text = "local a = 1\nprint(a)\n-- Decompiled by ALVSIA PRO"
        cleaned, count = scrub_foreign_branding(text)
        self.assertEqual(count, 0)
        self.assertEqual(cleaned, text)

    def test_empty_input_is_safe(self):
        self.assertEqual(scrub_foreign_branding(""), ("", 0))
        self.assertEqual(scrub_foreign_branding(None), (None, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
