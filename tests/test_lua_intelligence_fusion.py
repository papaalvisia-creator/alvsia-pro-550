import tempfile
import unittest
from pathlib import Path

from app.src.main.python.lua_intelligence.fusion import (
    FusionCandidate, fuse_candidates, semantic_equivalence,
)


class FusionTests(unittest.TestCase):
    def _source(self, root, name, text):
        path = Path(root) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_consensus_wins_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = self._source(root, "a.lua", "function f(x) return x + 1 end\n")
            b = self._source(root, "b.lua", "function f(x) return x + 1 end\n")
            c = self._source(root, "c.lua", "return totally unrelated value\n")
            decision = fuse_candidates([
                FusionCandidate("engine_a", a),
                FusionCandidate("engine_b", b),
                FusionCandidate("engine_c", c),
            ])
            self.assertEqual(decision.status, "CONSENSUS")
            self.assertIn(decision.selected_engine, {"engine_a", "engine_b"})
            self.assertNotEqual(decision.selected_engine, "engine_c")
            self.assertGreaterEqual(decision.agreement[decision.selected_engine], 1)

    def test_single_candidate_can_never_claim_consensus(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._source(td, "only.lua", "return 42\n")
            decision = fuse_candidates([FusionCandidate("only", p)])
            self.assertNotEqual(decision.status, "CONSENSUS")
            self.assertEqual(decision.selected_engine, "only")
            self.assertEqual(decision.agreement["only"], 0)

    def test_bad_candidates_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._source(td, "bad.lua", "function f(x) return (x + 1 end\n")
            decision = fuse_candidates([FusionCandidate("bad", p)])
            self.assertEqual(decision.status, "FAILED")
            self.assertIsNone(decision.selected_engine)

    def test_semantic_equivalence_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            a = self._source(td, "a.lua", "local x = 1\nfunction f(a) return a + x end\n")
            b = self._source(td, "b.lua", "local y = 99\nfunction f(a) return a + y end\n")
            c = self._source(td, "c.lua", "return 1\n")
            self.assertTrue(semantic_equivalence(a, b))
            self.assertFalse(semantic_equivalence(a, c))


if __name__ == "__main__":
    unittest.main()
