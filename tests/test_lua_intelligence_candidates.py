import tempfile, unittest
from pathlib import Path
from app.src.main.python.lua_intelligence.candidates import score_source_candidate, rank_candidates

class CandidateTests(unittest.TestCase):
    def test_valid_lua_like_candidate_gets_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"out.lua"
            p.write_text("local function f(x) if x then return x end end\n",encoding="utf-8")
            c=score_source_candidate(p,dialect="lua-5.3",engine="fixture")
            self.assertGreater(c.rank(),0.5)
            self.assertEqual(c.status,"PARTIAL")
            self.assertTrue(c.metadata["balanced"])

    def test_large_candidate_is_scanned_without_full_file_read(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"large.lua"
            with p.open("wb") as f:
                for _ in range(200):
                    f.write(b"local function f(x) return x end\n")
            c=score_source_candidate(p)
            self.assertEqual(c.metadata["bytes"], p.stat().st_size)
            self.assertGreater(c.metadata["tokens"], 100)
            self.assertTrue(c.metadata["balanced"])

    def test_invalid_empty_candidate_is_failed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"empty.lua"; p.write_bytes(b"")
            c=score_source_candidate(p)
            self.assertEqual(c.status,"FAILED")
            self.assertEqual(c.rank(),0.0)

    def test_ranking_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.lua"; b=Path(td)/"b.txt"
            a.write_text("return function(x) return x end\n",encoding="utf-8")
            b.write_text("not lua at all",encoding="utf-8")
            out=rank_candidates([score_source_candidate(b),score_source_candidate(a)])
            self.assertEqual(out[0].path,str(a))

if __name__=="__main__":
    unittest.main()
