import tempfile, unittest
from pathlib import Path
from app.src.main.python.lua_intelligence.ir import (
    ProgramIR, IRFunction, IRInstruction, validate_ir, ir_from_source, ir_from_bytecode_header
)
from app.src.main.python.lua_intelligence.structure import analyze_bytecode_structure

class IRTests(unittest.TestCase):
    def test_source_adapter_and_validation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.lua"; p.write_text("function alpha(a,b) return a+b end\n",encoding="utf-8")
            ir=ir_from_source(p,dialect="lua-5.3",artifact_id="a-test")
            self.assertEqual(ir.functions[0].params,2)
            self.assertTrue(validate_ir(ir).valid)

    def test_bytecode_header_adapter_is_conservative(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.luac"; p.write_bytes(b"\x1bLua\x54\x00\x19\x93\r\n\x1a\n"+b"X"*32)
            ir=ir_from_bytecode_header(p,"lua-5.4","a-test")
            self.assertEqual(ir.functions[0].instructions[0].opcode,"BYTECODE_MODULE")
            self.assertEqual(validate_ir(ir).valid,True)
            s=analyze_bytecode_structure(p,"lua-5.4")
            self.assertTrue(s.valid_header)
            self.assertEqual(s.sections[0],"puc-lua-header")


    def test_lua53_header_metadata_is_decoded_without_instruction_execution(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.luac"
            header = (
                b"\x1bLua\x53\x00\x01\x04\x04\x04\x08\x08\x00"
                + b"\\x01" * 8
                + b"\\x00" * 8
                + b"\\x00" * 5
            )
            p.write_bytes(header + b"\x00" * 128)
            s = analyze_bytecode_structure(p, "lua-5.3")
            self.assertTrue(s.valid_header)
            self.assertEqual(s.version, "Lua 5.3")
            self.assertEqual(s.instruction_size, 4)
            self.assertEqual(s.payload_offset, 33)
            self.assertIn("bytecode-payload", s.sections)


    def test_invalid_ir_rejected(self):
        ir=ProgramIR(functions=[IRFunction("x",instructions=[IRInstruction("",confidence=2.0)])])
        v=validate_ir(ir)
        self.assertFalse(v.valid)
        self.assertTrue(v.errors)

if __name__=="__main__":
    unittest.main()
