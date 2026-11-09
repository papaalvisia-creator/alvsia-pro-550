import tempfile
import unittest
from pathlib import Path

from app.src.main.python.lua_intelligence.oracle import (
    compile_trusted_fixture,
    differential_validate,
    parse_source,
)


class TestOracle(unittest.TestCase):
    def test_parser_accepts_large_stream_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "large.lua"
            body = "local x = 1\nfunction f(a) if a then return a + x end end\n"
            p.write_text(body * 100000, encoding="utf-8")
            r = parse_source(p)
            self.assertTrue(r.ok)
            self.assertGreater(r.details["bytes"], 5_000_000)

    def test_parser_rejects_unbalanced(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.lua"
            p.write_text("function f(x) return (x + 1 end", encoding="utf-8")
            self.assertFalse(parse_source(p).ok)

    def test_differential_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.lua"
            b = Path(td) / "b.lua"
            a.write_text("local function f(x) return x + 1 end", encoding="utf-8")
            b.write_text("function f(x) return x + 1 end", encoding="utf-8")
            r1 = differential_validate(a, b)
            r2 = differential_validate(a, b)
            self.assertEqual(r1.score, r2.score)
            self.assertTrue(r1.ok)

    def test_compiler_is_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "fixture.lua"
            p.write_text("return 1", encoding="utf-8")
            r = compile_trusted_fixture(p, compiler=None)
            self.assertFalse(r.ok)
            self.assertEqual(r.details["status"], "not_configured")


if __name__ == "__main__":
    unittest.main()
