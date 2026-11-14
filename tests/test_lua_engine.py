import json, tempfile, zlib, struct
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))
from lua_engine import detect_lua, analyze_lua, validate_lua_source, unwrap_lua_container, decompile_lua
from lua_engine.bgmi import is_bgmi_lua, transform_bgmi_lua

def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        src=td/"sample.lua"
        src.write_text('local function add(a,b) return a+b end\nreturn add(2,3)\n', encoding="utf-8")
        info=detect_lua(src)
        assert info.kind=="source" and info.format=="lua-source"
        ok,msg=validate_lua_source(src)
        assert ok, msg

        # Structural validation must treat for/while's "do" as part of the
        # loop block and ignore Lua keywords inside strings and comments.
        loop_source = td / "loop_valid.lua"
        loop_source.write_text(
            'local function work(items)\n'
            '  for i = 1, #items do\n'
            '    while items[i] do\n'
            '      do local marker = "end function if" end\n'
            '      items[i] = nil\n'
            '    end\n'
            '  end\n'
            '  repeat local done = true until done\n'
            '  -- end end end (comment only)\n'
            '  local text = [=[function fake() end]=]\n'
            '  return text\n'
            'end\n'
            'return work\n',
            encoding="utf-8",
        )
        loop_ok, loop_msg = validate_lua_source(loop_source)
        assert loop_ok, loop_msg
        malformed_source = (
            'local function broken()\n'
            '  for i = 1, 3 do return i\n'
            'end\n'
        )
        malformed_ok, malformed_msg = validate_lua_source(malformed_source)
        assert not malformed_ok and ("unclosed" in malformed_msg or "parser rejected" in malformed_msg), malformed_msg

        # When the matching compiler is installed, parser validation must
        # reject syntax errors that balanced block keywords cannot detect.
        parser_invalid = td / "parser_invalid.lua"
        parser_invalid.write_text("local = 1\\nreturn 1\\n", encoding="utf-8")
        parser_ok, parser_msg = validate_lua_source(
            parser_invalid, expected_version="Lua 5.3"
        )
        assert not parser_ok and "parser rejected" in parser_msg, parser_msg
        parser_valid, parser_valid_msg = validate_lua_source(
            src, expected_version="Lua 5.3"
        )
        assert parser_valid and "parser accepted" in parser_valid_msg, parser_valid_msg
        report=analyze_lua(src,td)
        assert report["ok"] and report["format"]=="lua-source"
        luac=td/"sample.luac"; luac.write_bytes(bytes.fromhex("1b4c756153") + bytes(32))
        li=detect_lua(luac)
        assert li.format=="luac" and li.version=="Lua 5.3"

        lua55 = td / "sample_lua55.luac"
        lua55.write_bytes(bytes.fromhex("1b4c75615500") + bytes(40))
        li55 = detect_lua(lua55)
        assert li55.format == "luac" and li55.version == "Lua 5.5", li55

        # Luau has a distinct version/type/string-table/proto header and must
        # not be mistaken for PUC Lua bytecode or arbitrary binary data.
        luau = td / "sample.luau"
        luau.write_bytes(bytes((13, 3, 0, 0, 1, 0, 0)))
        luau_info = detect_lua(luau)
        assert luau_info.format == "luau" and luau_info.version == "Luau bytecode v13", luau_info
        luau_v7 = td / "sample_v7.luau"
        luau_v7.write_bytes(bytes((7, 3, 0, 0, 1, 0, 0)))
        luau_v7_info = detect_lua(luau_v7)
        assert luau_v7_info.format == "luau" and luau_v7_info.version == "Luau bytecode v7", luau_v7_info
        truncated_luau = td / "truncated_luau.bin"
        truncated_luau.write_bytes(bytes((13, 3, 0, 1)))
        assert detect_lua(truncated_luau).format == "unknown"

        # Decompile dispatch must initialize its output/backend state for
        # bytecode inputs even when no external unluac JAR is configured.
        decompile_report = decompile_lua(luac, td / "decompile_out", jars_dir=td / "missing_jars")
        assert isinstance(decompile_report, dict) and "ok" in decompile_report, decompile_report
        assert "UnboundLocalError" not in str(decompile_report), decompile_report
        assert "NameError" not in str(decompile_report), decompile_report

        short_source = td / "short.lua"
        short_source.write_text("print(1)\\n", encoding="utf-8")
        source_report = decompile_lua(short_source, td / "source_out")
        assert source_report.get("ok") and source_report.get("mode") == "source_passthrough", source_report
        lj=td/"sample.lj"; lj.write_bytes(bytes.fromhex("1b4c4a02") + bytes(20))
        ji=detect_lua(lj)
        assert ji.format=="luajit"
        assert ji.version=="LuaJIT 2.1", ji
        lj20=td/"sample_lj20.lj"; lj20.write_bytes(bytes.fromhex("1b4c4a01") + bytes(20))
        ji20=detect_lua(lj20)
        assert ji20.version=="LuaJIT 2.0", ji20

        # Comment-prefixed bytecode must be identified and normalized for
        # Smart Decompile instead of being mistaken for an unknown text file.
        prefixed = td/"prefixed.lua"
        prefixed.write_bytes(
            b"-- exported by a Lua tool\n-- metadata\n"
            + b"\x1bLua\x53\x00" + b"\x19\x93\x0d\x0a\x1a\x0a"
            + bytes(32)
        )
        pi=detect_lua(prefixed)
        assert pi.kind=="bytecode" and pi.format=="luac", pi
        assert any(n.startswith("comment_prefix_offset=") for n in pi.notes), pi
        arbitrary = td/"embedded.bin"
        arbitrary.write_bytes(b"BIN\x00garbage\x1bLua\x53" + bytes(32))
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

        # Structure-only BGMI conversion must preserve arbitrary encrypted
        # string bytes exactly when no authorized XOR key is supplied.
        standard_bgmi_header = (
            b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
            + b"\x04\x08\x04\x08\x08"
            + bytes.fromhex("7856000000000000")
            + bytes.fromhex("0000000000287740")
        )
        standard_bgmi_chunk = (
            standard_bgmi_header
            + struct.pack("<B", 0)              # main upvalue count
            + struct.pack("<B", 0)              # source = NULL
            + struct.pack("<ii", 0, 0)          # line-defined / last-line
            + struct.pack("<BBB", 0, 0, 2)      # params / vararg / stack
            + struct.pack("<I", 1)              # one instruction
            + struct.pack("<I", 38)             # RETURN
            + struct.pack("<I", 1)              # one constant
            + struct.pack("<BB", 4, 4)          # short string, size incl NUL
            + b"\xff\xfeA"                    # deliberately non-UTF8 bytes
            + struct.pack("<I", 0)              # upvalues
            + struct.pack("<I", 0)              # nested prototypes
            + struct.pack("<I", 0)              # line info
            + struct.pack("<I", 0)              # absolute line info
            + struct.pack("<I", 0)              # local variables
            + struct.pack("<I", 0)              # upvalue names
        )
        bgmi_structural = transform_bgmi_lua(
            standard_bgmi_chunk, key=None, decrypt=False
        )
        assert is_bgmi_lua(bgmi_structural)
        bgmi_roundtrip = transform_bgmi_lua(
            bgmi_structural, key=None, decrypt=True
        )
        assert bgmi_roundtrip == standard_bgmi_chunk

        # Keyed conversion must also preserve non-UTF8 Lua string bytes.
        fixture_key = b"unit-test-bgmi-key"
        encrypted_bgmi = transform_bgmi_lua(
            standard_bgmi_chunk, key=fixture_key, decrypt=False
        )
        keyed_roundtrip = transform_bgmi_lua(
            encrypted_bgmi, key=fixture_key, decrypt=True
        )
        assert keyed_roundtrip == standard_bgmi_chunk

        # The large-file streaming normalizer must reuse the one input buffer
        # across standard/mod-guard/BGMI candidates instead of rereading 30 MiB.
        from alvsia_private import ALVSIA_BGMI_XOR_KEY
        import lua_engine.decompiler53 as decompiler53
        from lua_engine.streaming_decompiler import stream_decompile_lua53
        canonical_bgmi = transform_bgmi_lua(
            standard_bgmi_chunk, key=ALVSIA_BGMI_XOR_KEY, decrypt=False
        )
        stream_bgmi_path = td / "sample_streaming.bgmi"
        stream_bgmi_path.write_bytes(canonical_bgmi)
        stream_bgmi_out = td / "sample_streaming.lua"
        original_read_bytes = Path.read_bytes
        read_count = 0

        def counted_read_bytes(path):
            nonlocal read_count
            if Path(path) == stream_bgmi_path:
                read_count += 1
            return original_read_bytes(path)

        def force_bgmi_normalization(candidate, **kwargs):
            candidate_bytes = bytes(candidate)
            if candidate_bytes[13] == 4:
                raise ValueError("fixture forces BGMI normalization")
            return "return"

        with patch.object(Path, "read_bytes", counted_read_bytes):
            with patch.object(decompiler53, "decompile_bytes", force_bgmi_normalization):
                stream_ok, stream_note = stream_decompile_lua53(
                    stream_bgmi_path, stream_bgmi_out
                )
        assert stream_ok, stream_note
        assert read_count == 1, f"large input was read {read_count} times"
        assert stream_bgmi_out.is_file()
        assert b"\xff\xfeA" in bgmi_roundtrip

        # The Smart Lua orchestrator may use this only as a last-resort,
        # explicitly PARTIAL candidate after ordinary engines reject the file.
        bgmi_path = td / "sample_structure_only.bgmi"
        bgmi_path.write_bytes(bgmi_structural)
        bgmi_source = td / "sample_structure_only.lua"
        from lua_engine.orchestrator import _run_bgmi_structure_only
        bgmi_ok, bgmi_note = _run_bgmi_structure_only(bgmi_path, bgmi_source)
        assert bgmi_ok, bgmi_note
        assert "structure-only" in bgmi_note
        bgmi_valid, bgmi_validation = validate_lua_source(
            bgmi_source, expected_version="Lua 5.3"
        )
        assert bgmi_valid, bgmi_validation

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
