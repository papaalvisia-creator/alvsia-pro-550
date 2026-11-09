import tempfile, unittest, zipfile
from pathlib import Path
from app.src.main.python.lua_intelligence.core import IntelligenceEngine, IntelligenceConfig

class IntelligenceCoreTests(unittest.TestCase):
    def test_lua_source_is_hashed_and_classified(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/"sample.lua"; src.write_text("return function(x) return x+1 end\n",encoding="utf-8")
            result=IntelligenceEngine().analyze(src,root/"out")
            self.assertTrue(result.ok)
            self.assertEqual(result.artifacts[0].dialect,"lua-family")
            self.assertEqual(len(result.artifacts[0].sha256),64)

    def test_recursive_zip_layer_graph(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); inner=root/"inner.lua"; inner.write_text("return 1\n",encoding="utf-8")
            z=root/"payload.zip"
            with zipfile.ZipFile(z,"w") as f: f.write(inner,"nested/inner.lua")
            result=IntelligenceEngine(IntelligenceConfig(max_depth=4)).analyze(z,root/"out")
            self.assertGreaterEqual(len(result.artifacts),2)
            self.assertTrue(result.artifacts[1].parent_id)

    def test_unknown_does_not_execute(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/"x.bin"; src.write_bytes(b"\x00"*100)
            result=IntelligenceEngine().analyze(src,root/"out")
            self.assertEqual(result.status,"PARTIAL")
            self.assertEqual(result.artifacts[0].status,"UNSUPPORTED")

if __name__=="__main__": unittest.main()
