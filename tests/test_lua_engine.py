import json, tempfile, zlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))
from lua_engine import detect_lua, analyze_lua, validate_lua_source, unwrap_lua_container
from lua_engine.bgmi import transform_bgmi_lua

def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        src=td/"sample.lua"
        src.write_text('local function add(a,b) return a+b end\nreturn add(2,3)\n', encoding="utf-8")
        info=detect_lua(src)
        assert info.kind=="source" and info.format=="lua-source"
        ok,msg=validate_lua_source(src)
        assert ok, msg
        report=analyze_lua(src,td)
        assert report["ok"] and report["format"]=="lua-source"
        luac=td/"sample.luac"; luac.write_bytes(bytes.fromhex("1b4c756153") + bytes(32))
        li=detect_lua(luac)
        assert li.format=="luac" and li.version=="Lua 5.3"
        lj=td/"sample.lj"; lj.write_bytes(bytes.fromhex("1b4c4a02") + bytes(20))
        ji=detect_lua(lj)
        assert ji.format=="luajit"

        # Comment-prefixed bytecode must be identified and normalized for
        # Smart Decompile instead of being mistaken for an unknown text file.
        prefixed = td/"prefixed.lua"
        prefixed.write_bytes(
            b"-- exported by a Lua tool\\n-- metadata\\n"
            + b"\\x1bLua\\x53\\x00" + b"\\x19\\x93\\x0d\\x0a\\x1a\\x0a"
            + bytes(32)
        )
        pi=detect_lua(prefixed)
        assert pi.kind=="bytecode" and pi.format=="luac", pi
        assert any(n.startswith("comment_prefix_offset=") for n in pi.notes), pi
        arbitrary = td/"embedded.bin"
        arbitrary.write_bytes(b"BIN\\x00garbage\\x1bLua\\x53" + bytes(32))
        assert detect_lua(arbitrary).kind=="unknown"
        bad=td/"bad.bin"; bad.write_bytes(bytes([0, 1]) + b"garbage")
        assert not analyze_lua(bad,td)["ok"]

        # Standard zlib has multiple valid FLG values; do not hard-code 78da.
        lua_payload = b"\x1bLuaS" + bytes(range(27))
        for level, expected_header in ((0, b"\x78\x01"), (6, b"\x78\x9c"), (9, b"\x78\xda")):
            wrapped = zlib.compress(lua_payload, level)
            assert wrapped.startswith(expected_header), (level, wrapped[:2].hex())
            unwrapped, ci = unwrap_lua_container(wrapped)
            assert unwrapped == lua_payload and ci.wrapped and ci.format == "zlib"
            sample_path = td / ("sample_" + str(level) + ".bin")
            sample_path.write_bytes(wrapped)
            detected = detect_lua(sample_path)
            assert detected.wrapped and detected.format == "luac", detected
            report = analyze_lua(sample_path, td / ("out_" + str(level)))
            assert report["ok"] and report["format"] == "luac", report
            assert report["container"] == "zlib", report
        plain, ci = unwrap_lua_container(lua_payload)
        assert plain == lua_payload and not ci.wrapped

        # Unknown BGMI opcodes must fail closed, never pass through as standard
        # Lua opcodes and create a misleading decompile result.
        bgmi_header = (
            b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
            + b"\x04\x04\x04\x08\x08"
            + bytes.fromhex("7856000000000000")
            + bytes.fromhex("0000000000287740")
        )
        assert len(bgmi_header) == 33
        # main upvalue, source=nil, line-defined, last-line, proto flags,
        # instruction count, then one raw instruction whose opcode is 6.
        import struct
        unknown_opcode_chunk = (
            bgmi_header
            + struct.pack("<B", 0)       # main upvalue count
            + struct.pack("<B", 0)       # nil source string
            + struct.pack("<ii", 0, 0)  # line-defined, last-line
            + struct.pack("<BBB", 0, 0, 0)  # proto flags
            + struct.pack("<I", 1)       # one instruction
            + struct.pack("<I", 6)       # unsupported opcode 6
        )
        try:
            transform_bgmi_lua(unknown_opcode_chunk)
        except ValueError as exc:
            assert "unsupported BGMI opcode 6" in str(exc)
        else:
            raise AssertionError("unknown BGMI opcode was silently normalized")

        # Enforce the expansion limit before buffering an oversized payload.
        oversized = zlib.compress(b"\x1bLuaS" + (b"A" * 10000), 9)
        try:
            unwrap_lua_container(oversized, max_output=128)
        except ValueError as exc:
            assert "exceeds output limit" in str(exc)
        else:
            raise AssertionError("oversized zlib payload was accepted")

    # Real wrapped Lua regression fixture: chunked 78da/raw-deflate container.
    real = Path("/mnt/data/CharacterBase.lua")
    if real.is_file():
        ri = detect_lua(real)
        assert ri.wrapped and ri.container == "chunked-raw-deflate" and ri.version == "Lua 5.3"
        payload, ci = __import__("lua_engine", fromlist=["unwrap_lua_container"]).unwrap_lua_container(real.read_bytes())
        assert payload.startswith(b"\x1bLuaS") and ci.chunks >= 1
    print("LUA ENGINE TEST: PASS")
if __name__=="__main__": main()
