"""Regression tests for the mod-guard sanitizer (protected mod-tool chunks).

The GOKU-style protected producer appends to every prototype two dead JMP
instructions after the real RETURN, and a plain-text banner after the chunk.
The sanitizer must patch the tails and split the banner while keeping every
instruction offset identical.
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.modguard import detect_mod_guard, sanitize_mod_guard


def _make_guarded_chunk(code_words, with_banner=True):
    header = (
        b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
        + bytes([4, 4, 4, 8, 8])
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
    )
    assert len(header) == 33
    out = bytearray(header)
    out.append(1)                      # main closure upvalue count
    out.extend(b"\x00")                # source name = null
    out.extend(struct.pack("<ii", 0, 0))
    out.extend(bytes([0, 0, 2]))       # params, vararg, maxstack
    out.extend(struct.pack("<I", len(code_words)))
    for word in code_words:
        out.extend(struct.pack("<I", word))
    out.extend(struct.pack("<I", 0))   # constants
    out.extend(struct.pack("<I", 0))   # upvalues
    out.extend(struct.pack("<I", 0))   # nested protos
    out.extend(struct.pack("<I", 0))   # lineinfo
    out.extend(struct.pack("<I", 0))   # abslineinfo
    out.extend(struct.pack("<I", 0))   # locals
    out.extend(struct.pack("<I", 0))   # upvalue names
    body = bytes(out)
    if with_banner:
        banner = b"\n-- PROTECTED MOD BANNER - DO NOT DECOMPILE\n"
        return body + banner
    return body


def _jmp(sbx):
    return 30 | (((sbx + 131071) & 0x3FFFF) << 14)


RETURN = 38 | (1 << 23)
LOADK_RET = 1 | (1 << 22)  # dummy instruction


def test_detect_and_sanitize_guarded_chunk():
    # tail: [..., RETURN, JMP(-10), JMP(+50)]
    code = [LOADK_RET, RETURN, _jmp(-10), _jmp(50)]
    guarded = _make_guarded_chunk(code, with_banner=True)
    report = detect_mod_guard(guarded)
    assert report and report.get("detected")
    assert report.get("banner_bytes") > 0
    assert report.get("dead_tail_protos", 0) >= 1

    clean, mg = sanitize_mod_guard(guarded)
    assert mg.get("applied")
    assert mg.get("patched_protos") == 1
    # chunk shrinks by exactly the banner length; instruction count unchanged
    assert len(clean) == len(guarded) - report["banner_bytes"]
    # Code section: 33(header)+1(upc)+1(src)+8(lines)+3(bytes)+4(count) = 50
    code_off = 50
    words = [struct.unpack_from("<I", clean, code_off + 4 * i)[0] for i in range(4)]
    assert [w & 0x3F for w in words] == [1, 38, 30, 38]
    # the dead forward jump became RETURN(A=0, B=1); back-jump untouched
    assert words[3] == 38 | (1 << 22)  # RETURN A=0 B=1
    assert words[2] == _jmp(-10)


def test_unguarded_chunk_passes_through_untouched():
    code = [LOADK_RET, RETURN]
    plain = _make_guarded_chunk(code, with_banner=False)
    assert detect_mod_guard(plain) is None
    clean, mg = sanitize_mod_guard(plain)
    assert not mg.get("applied")
    assert clean == plain


def test_banner_only_is_not_a_guard_signature():
    # A chunk that ends cleanly with RETURN and has trailing text is NOT
    # patched: the dead-tail signature is required.
    code = [LOADK_RET, RETURN]
    chunk = _make_guarded_chunk(code, with_banner=False)
    report = detect_mod_guard(chunk)
    assert report is None


def test_sanitized_chunk_still_parses_as_lua53():
    from lua_engine.decompiler53 import load_chunk
    code = [LOADK_RET, RETURN, _jmp(-10), _jmp(50)]
    guarded = _make_guarded_chunk(code, with_banner=True)
    clean, mg = sanitize_mod_guard(guarded)
    assert mg.get("applied")
    # The patched chunk must be structurally valid for the strict reader.
    load_chunk(clean)


def test_non_luac_input_is_ignored():
    assert detect_mod_guard(b"plain text file") is None
    assert detect_mod_guard(b"") is None
    clean, mg = sanitize_mod_guard(b"plain text file")
    assert clean == b"plain text file"
    assert not mg.get("applied")
