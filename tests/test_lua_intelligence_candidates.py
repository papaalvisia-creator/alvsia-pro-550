import tempfile, unittest
from pathlib import Path
from app.src.main.python.lua_intelligence.candidates import score_source_candidate, rank_candidates

class CandidateTests(unittest.TestCase):
    def test_valid_lua_like_candidate_gets_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"out.lua"; p.write_text("local function f(x) if x then return x end end\n",encoding="utf-8")
            c=score_source_candidate(p,dialect="lua-5.3",engine="fixture")
            self.assertGreater(c.rank(),0.5)
            self.assertEqual(c.status,"PARTIAL")

    def test_ranking_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.lua"; b=Path(td)/"b.txt"
            a.write_text("return function(x) return x end\n",encoding="utf-8")
            b.write_text("not lua at all",encoding="utf-8")
            out=rank_candidates([score_source_candidate(b),score_source_candidate(a)])
            self.assertEqual(out[0].path,str(a))

if __name__=="__main__": unittest.main()
