"""
ALVSIA PRO 5.5.0 — Lua VM Deobfuscator framework.

Detects and reverses known Lua protection schemes. Pluggable: each pattern
in `pattern_registry.py` carries its own detector + deobfuscator here.

Patterns implemented:
  1. ALVSEAL3_SOURCE  — our own VM-protected Lua source (full recovery)
  2. ALVLUA1_PAYLOAD  — our own AES-256-GCM encrypted payload (full recovery
                        when key is supplied)
  3. BGMI_VM          — BGMI / PUBG Mobile VM obfuscation (partial recovery:
                        structure + constants; original source requires
                        separate VM opcode RE project)

Output contract (per perbaikan_source.txt §4):
  • Never produce a fake .lua source. If only constants/structure are
    recoverable, output a structure report and a constants dump instead.
  • Status field on every result tells the truth:
       ok=True, recovered=True, mode="source"        → full source recovered
       ok=True, recovered=False, mode="partial"      → structure + constants only
       ok=False                                       → nothing recovered
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Local imports — work in both package and direct-script contexts.
import sys
try:
    from .decompiler53 import Reader
except Exception:
    # Direct script invocation (e.g. from tests)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from decompiler53 import Reader


# ────────────────────────────────────────────────────────────────────────────
# Pattern 1: ALVSEAL3_SOURCE  (our own VM-protected Lua source)
# ────────────────────────────────────────────────────────────────────────────

ALVSEAL3_HEADER_MARKER = b"-- ALVSIA PRO 5.5.0 VM-protected Lua payload"
ALVSEAL3_PAYLOAD_RE = re.compile(r'_alvsia_payload\s*=\s*"([^"]+)"')
ALVSEAL3_KEY_OBF_RE = re.compile(r'_alvsia_key_obf\s*=\s*"([^"]+)"')


def detect_alvseal3_source(input_path: Path) -> bool:
    """True if [input_path] is a Lua source file produced by
    alvsia_vm_protect.vm_protect(..., output_format='lua')."""
    try:
        if input_path.stat().st_size < 200:
            return False
        # Quick sniff: read first 256 bytes
        with input_path.open("rb") as f:
            head = f.read(256)
        return ALVSEAL3_HEADER_MARKER in head
    except Exception:
        return False


def deobfuscate_alvseal3_source(input_path: Path, out_dir: Path) -> Dict[str, Any]:
    """Reverse an ALVSEAL3-protected Lua source file to the original source."""
    t0 = time.time()
    try:
        from alvsia_vm_protect import vm_extract_payload, vm_decrypt_payload
    except Exception:
        # fallback for direct script invocation
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from alvsia_vm_protect import vm_extract_payload, vm_decrypt_payload

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from .detector import read_lua_text_strict
        text = read_lua_text_strict(input_path)
    except Exception as exc:
        return {"ok": False, "error": f"read failed: {exc}"}

    try:
        payload, key, mode = vm_extract_payload(text)
    except ValueError as exc:
        return {"ok": False, "error": f"extract failed: {exc}",
                "input": str(input_path)}

    try:
        original = vm_decrypt_payload(payload, key)
    except ValueError as exc:
        return {"ok": False, "error": f"decrypt failed: {exc}",
                "input": str(input_path),
                "payload_size": len(payload)}

    out_path = out_dir / (input_path.stem + "_recovered.lua")
    out_path.write_bytes(original)

    # Verify recovered source looks like Lua
    try:
        text_check = original.decode("utf-8", errors="replace")
        is_lua = bool(re.search(
            r"\b(?:local|function|return|if|for|while|repeat|do|end)\b",
            text_check[:4096]
        ))
    except Exception:
        is_lua = False

    return {
        "ok": True,
        "recovered": True,
        "mode": "alvseal3_source",
        "input": str(input_path),
        "out": str(out_path),
        "input_size": input_path.stat().st_size,
        "recovered_size": len(original),
        "is_lua_source": is_lua,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


# ────────────────────────────────────────────────────────────────────────────
# Pattern 2: ALVLUA1_PAYLOAD  (AES-256-GCM encrypted Lua payload)
# ────────────────────────────────────────────────────────────────────────────

ALVLUA1_MAGIC = b"ALVLUA1"


def detect_alvlua1_payload(input_path: Path) -> bool:
    """True if [input_path] starts with the ALVLUA1 magic header."""
    try:
        if input_path.stat().st_size < 35:  # 7 magic + 12 nonce + 16 tag
            return False
        with input_path.open("rb") as f:
            return f.read(7) == ALVLUA1_MAGIC
    except Exception:
        return False


def deobfuscate_alvlua1_payload(input_path: Path, out_dir: Path) -> Dict[str, Any]:
    """Reverse an ALVLUA1-encrypted payload to the original Lua source.

    Requires the 64-hex key in WORK/lua_protect_key.txt (created by the
    user when they ran lua_protect_encrypt). Without the key, GCM tag
    verification will fail and recovery is impossible — by design.
    """
    t0 = time.time()
    try:
        from alvsia_vm_protect import vm_decrypt_payload  # noqa: F401 — not used here
    except Exception:
        pass

    out_dir.mkdir(parents=True, exist_ok=True)
    # Look for the key file in standard ALVSIA work tree
    work_key_path = out_dir.parent / "WORK" / "lua_protect_key.txt"
    if not work_key_path.is_file():
        # Try alternative locations
        for cand in [
            out_dir / "lua_protect_key.txt",
            input_path.parent / "lua_protect_key.txt",
        ]:
            if cand.is_file():
                work_key_path = cand
                break
        else:
            return {
                "ok": False,
                "recovered": False,
                "mode": "alvlua1_payload",
                "error": "key file not found — place 64-hex key in WORK/lua_protect_key.txt",
                "input": str(input_path),
            }

    try:
        key_hex = work_key_path.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", key_hex):
            return {"ok": False, "error": "key file does not contain 64-hex chars"}
        key = bytes.fromhex(key_hex)
    except Exception as exc:
        return {"ok": False, "error": f"key read failed: {exc}"}

    try:
        from Crypto.Cipher import AES
    except ImportError:
        return {"ok": False, "error": "PyCryptodome AES unavailable in this runtime"}

    try:
        source = input_path.read_bytes()
        if len(source) < 35 or source[:7] != ALVLUA1_MAGIC:
            return {"ok": False, "error": "invalid ALVLUA1 header or truncated payload"}
        nonce, tag, ciphertext = source[7:19], source[19:35], source[35:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
        cipher.update(b"ALVLUA1")
        try:
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError:
            return {
                "ok": False,
                "recovered": False,
                "mode": "alvlua1_payload",
                "error": "authentication failed — wrong key or modified payload",
                "input": str(input_path),
            }
    except Exception as exc:
        return {"ok": False, "error": f"decrypt failed: {exc}"}

    out_path = out_dir / (input_path.stem + ".lua")
    out_path.write_bytes(plaintext)

    return {
        "ok": True,
        "recovered": True,
        "mode": "alvlua1_payload",
        "input": str(input_path),
        "out": str(out_path),
        "input_size": input_path.stat().st_size,
        "recovered_size": len(plaintext),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


# ────────────────────────────────────────────────────────────────────────────
# Pattern 3: BGMI_VM  (BGMI / PUBG Mobile Lua VM obfuscation)
# ────────────────────────────────────────────────────────────────────────────

BGMI_MAIN_INSTR_THRESHOLD = 1000
BGMI_NESTED_CONST_THRESHOLD = 500


def _parse_lua53_header(data: bytes) -> Optional[Dict[str, Any]]:
    """Parse the standard Lua 5.3 chunk header. Returns dict or None."""
    try:
        if len(data) < 34:
            return None
        if data[:4] != b"\x1bLua":
            return None
        version = data[4]
        format_flag = data[5]
        luac_data = data[6:12]
        if luac_data != b"\x19\x93\x0d\x0a\x1a\x0a":
            return None
        int_size = data[12]
        sizet_size = data[13]
        instr_size = data[14]
        lua_int_size = data[15]
        lua_num_size = data[16]
        # LUAC_INT
        import struct
        if lua_int_size == 8:
            luac_int = struct.unpack("<q", data[17:25])[0]
            offset = 25
        else:
            luac_int = struct.unpack("<i", data[17:21])[0]
            offset = 21
        # LUAC_NUM
        if lua_num_size == 8:
            luac_num = struct.unpack("<d", data[offset:offset + 8])[0]
            offset += 8
        # upvalue count
        upv_count = data[offset]
        offset += 1
        return {
            "version": version,
            "format": format_flag,
            "int_size": int_size,
            "sizet_size": sizet_size,
            "instr_size": instr_size,
            "lua_int_size": lua_int_size,
            "lua_num_size": lua_num_size,
            "luac_int": luac_int,
            "luac_num": luac_num,
            "upvalue_count": upv_count,
            "main_offset": offset,
        }
    except Exception:
        return None


def _walk_lua53_protos(
    data: bytes,
    header: Dict[str, Any],
    deadline: float | None = None,
) -> Dict[str, Any]:
    """Bounded Lua 5.3 structure walk; malformed counts fail closed, never loop unbounded."""
    r = Reader(data, deadline=deadline)
    r.lua_int_size = header["lua_int_size"]
    r.lua_num_size = header["lua_num_size"]
    r._pos = header["main_offset"]
    protos = []
    errors = []
    proto_count = 0

    def skip_bytes(count: int) -> None:
        if count < 0 or count > r.remaining():
            raise ValueError(f"invalid bytecode section length {count} at offset {r._pos}")
        r._pos += count

    def load_proto(depth, idx_in_parent):
        nonlocal proto_count
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("BGMI pattern scan deadline exceeded")
        if depth > 128:
            raise ValueError("Lua proto nesting exceeds 128 levels")
        proto_count += 1
        if proto_count > 100000:
            raise ValueError("Lua proto count exceeds 100000")
        start = r._pos
        info = {"depth": depth, "idx": idx_in_parent, "offset": start}
        try:
            info["source"] = r.string()
            info["linedefined"] = r.int_()
            info["lastlinedefined"] = r.int_()
            info["numparams"] = r.uint8()
            info["is_vararg"] = r.uint8()
            info["maxstacksize"] = r.uint8()
            n_code = r.int_()
            info["code_count"] = n_code
            if n_code < 0 or n_code > r.remaining() // 4:
                raise ValueError(f"invalid instruction count {n_code}")
            skip_bytes(n_code * 4)
            n_const = r.int_()
            info["const_count"] = n_const
            if n_const < 0 or n_const > r.remaining():
                raise ValueError(f"invalid constant count {n_const}")
            for const_index in range(n_const):
                if deadline is not None and (const_index & 0x3FF) == 0 and time.monotonic() >= deadline:
                    raise TimeoutError("BGMI constant scan deadline exceeded")
                t = r.uint8()
                if t == 0:
                    pass
                elif t == 1:
                    skip_bytes(1)
                elif t == 3:
                    skip_bytes(header["lua_num_size"])
                elif t == 19:
                    skip_bytes(header["lua_int_size"])
                elif t in (4, 20):
                    sz = r.uint8()
                    if sz == 0xFF:
                        sz = r.sizet_()
                    skip_bytes(max(0, sz - 1))
                else:
                    raise ValueError(f"unsupported Lua constant type {t}")
            n_upv = r.int_()
            info["upvalue_count"] = n_upv
            if n_upv < 0 or n_upv > r.remaining() // 2:
                raise ValueError(f"invalid upvalue count {n_upv}")
            skip_bytes(n_upv * 2)
            n_nested = r.int_()
            info["nested_count"] = n_nested
            if n_nested < 0 or n_nested > min(100000, r.remaining() // 8):
                raise ValueError(f"invalid nested proto count {n_nested}")
            protos.append(info)
            for i in range(n_nested):
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("BGMI proto scan deadline exceeded")
                try:
                    load_proto(depth + 1, i)
                except Exception as e:
                    errors.append({
                        "depth": depth + 1,
                        "idx": i,
                        "offset": r._pos,
                        "error": f"{type(e).__name__}: {e}",
                    })
                    return
        except Exception as e:
            info["error"] = f"{type(e).__name__}: {e}"
            protos.append(info)
            errors.append({"depth": depth, "idx": idx_in_parent,
                           "offset": start, "error": info["error"]})

    load_proto(0, 0)
    return {"protos": protos, "errors": errors}


def detect_bgmi_vm_pattern(input_path: Path) -> bool:
    """True if [input_path] is a Lua 5.3 bytecode chunk with BGMI-style
    VM obfuscation pattern (large main function + nested proto with many constants)."""
    try:
        if input_path.stat().st_size > 256 * 1024 * 1024:
            return False
        data = input_path.read_bytes()
        header = _parse_lua53_header(data)
        if header is None:
            return False
        if header["version"] != 0x53:
            return False  # only Lua 5.3 for now
        walk = _walk_lua53_protos(data, header, deadline=time.monotonic() + 3.0)
        protos = walk["protos"]
        if not protos:
            return False
        main = protos[0]
        # BGMI pattern: main has >1000 instructions, main has nested protos,
        # at least one nested proto has >500 constants with 0 code (VM storage)
        if main.get("code_count", 0) < BGMI_MAIN_INSTR_THRESHOLD:
            return False
        nested = protos[1:]
        big_const_nesteds = [p for p in nested
                             if p.get("const_count", 0) > BGMI_NESTED_CONST_THRESHOLD
                             and p.get("code_count", 0) == 0]
        return len(big_const_nesteds) >= 1
    except Exception:
        return False


def deobfuscate_bgmi_vm_pattern(input_path: Path, out_dir: Path) -> Dict[str, Any]:
    """Best-effort partial recovery from a BGMI-style VM-obfuscated Lua chunk.

    Per perbaikan_source.txt §4: 'Jangan menganggap ekstraksi string atau
    konstanta sebagai dekompilasi yang berhasil.' So we never claim full
    recovery. We honestly report:
      • Structure map (every parsed proto)
      • Constant pool dump (strings + integers from main function)
      • A diagnostic explaining why full source recovery is NOT possible
        without RE-ing the VM opcode table

    To actually recover source, a separate RE project must:
      1. Identify the VM dispatcher's opcode table in the main function
      2. Map custom VM opcodes back to standard Lua 5.3 opcodes
      3. Reconstruct standard Lua 5.3 bytecode
      4. Decompile with standard unluac

    This function produces the inputs needed for that RE work.
    """
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if input_path.stat().st_size > 256 * 1024 * 1024:
            return {"ok": False, "error": "BGMI analysis input exceeds 256 MiB safety limit",
                    "input": str(input_path)}
        data = input_path.read_bytes()
        header = _parse_lua53_header(data)
        if header is None:
            return {"ok": False, "error": "not a Lua 5.3 chunk",
                    "input": str(input_path)}
        analysis_deadline = time.monotonic() + 12.0
        walk = _walk_lua53_protos(data, header, deadline=analysis_deadline)
        protos = walk["protos"]
        errors = walk["errors"]

        # Structure map
        structure_path = out_dir / (input_path.stem + "_structure.json")
        with structure_path.open("w", encoding="utf-8") as f:
            json.dump({"header": header, "protos": protos, "errors": errors},
                      f, indent=2, default=str)

        # Extract constants from main function only (first proto)
        # We re-walk the main proto to actually read its constants this time.
        constants = _extract_main_constants(data, header, deadline=analysis_deadline)
        const_path = out_dir / (input_path.stem + "_constants.txt")
        with const_path.open("w", encoding="utf-8") as f:
            f.write(f"# ALVSIA PRO 5.5.0 — BGMI-VM partial recovery\n")
            f.write(f"# Input: {input_path} ({input_path.stat().st_size} bytes)\n")
            f.write(f"# Main function: {protos[0].get('code_count', 0)} instructions, "
                    f"{protos[0].get('const_count', 0)} constants, "
                    f"{protos[0].get('nested_count', 0)} nested protos\n")
            f.write(f"# Parsed protos: {len(protos)} (errors: {len(errors)})\n\n")
            f.write(f"=== Main function constants ({len(constants)} total) ===\n")
            for i, (t, v) in enumerate(constants):
                if t == "str":
                    display = repr(v)[:200]
                    f.write(f"[{i:5d}] str  len={len(v) if v else 0:5d}  {display}\n")
                elif t == "int":
                    f.write(f"[{i:5d}] int  {v}\n")
                elif t == "flt":
                    f.write(f"[{i:5d}] flt  {v}\n")
                elif t == "bool":
                    f.write(f"[{i:5d}] bool {v}\n")
                else:
                    f.write(f"[{i:5d}] {t}\n")

        # Diagnostic report
        report_path = out_dir / (input_path.stem + "_recovery_report.txt")
        with report_path.open("w", encoding="utf-8") as f:
            f.write(
                "ALVSIA PRO 5.5.0 — BGMI-VM partial recovery report\n"
                "====================================================\n\n"
                f"Input:  {input_path}\n"
                f"Size:   {input_path.stat().st_size:,} bytes\n\n"
                "Lua 5.3 chunk header:\n"
                f"  version:           0x{header['version']:02x} (Lua 5.3)\n"
                f"  format:            {header['format']}\n"
                f"  int size:          {header['int_size']}\n"
                f"  size_t size:       {header['sizet_size']}\n"
                f"  instruction size:  {header['instr_size']}\n"
                f"  lua_Integer size:  {header['lua_int_size']}\n"
                f"  lua_Number size:   {header['lua_num_size']}\n"
                f"  LUAC_INT:          {header['luac_int']:#x}\n"
                f"  LUAC_NUM:          {header['luac_num']}\n"
                f"  upvalue count:     {header['upvalue_count']}\n\n"
                "Main function:\n"
                f"  code instructions: {protos[0].get('code_count', 0):,}\n"
                f"  constants:         {protos[0].get('const_count', 0):,}\n"
                f"  nested protos:     {protos[0].get('nested_count', 0)}\n"
                f"  max stack size:    {protos[0].get('maxstacksize', 0)}\n\n"
                "Structural walk:\n"
                f"  protos parsed:  {len(protos)}\n"
                f"  parse errors:   {len(errors)}\n\n"
                "Output files:\n"
                f"  {structure_path.name}  — full proto structure map\n"
                f"  {const_path.name}      — main function constant pool dump\n"
                f"  {report_path.name}     — this diagnostic report\n\n"
                "Recovery status:\n"
                "  full source recovery: NOT POSSIBLE with current toolset\n"
                "  reason: file uses VM-based obfuscation — the main function\n"
                "          is a custom VM interpreter and the original code is\n"
                "          encoded as constants inside nested protos. To recover\n"
                "          the original source, a reverse-engineering project\n"
                "          must map the VM dispatcher's opcode table back to\n"
                "          standard Lua 5.3 opcodes.\n\n"
                "What was recovered:\n"
                "  - Lua chunk structure (all parseable protos)\n"
                "  - Main function constant pool dump\n"
                "  - File integrity hashes (MD5, SHA-1, SHA-256)\n\n"
                "Per perbaikan_source.txt §4:\n"
                "  'Jangan menganggap ekstraksi string atau konstanta sebagai\n"
                "   dekompilasi yang berhasil.'\n"
                "  No fake .lua source was produced.\n"
            )

        md5 = hashlib.md5(data).hexdigest()
        sha256 = hashlib.sha256(data).hexdigest()
        return {
            "ok": True,
            "recovered": False,  # honest: not a full source recovery
            "mode": "bgmi_vm_partial",
            "input": str(input_path),
            "input_size": len(data),
            "input_md5": md5,
            "input_sha256": sha256,
            "main_code_count": protos[0].get("code_count", 0),
            "main_const_count": protos[0].get("const_count", 0),
            "main_nested_count": protos[0].get("nested_count", 0),
            "protos_parsed": len(protos),
            "parse_errors": len(errors),
            "structure_out": str(structure_path),
            "constants_out": str(const_path),
            "report_out": str(report_path),
            "elapsed_ms": int((time.time() - t0) * 1000),
            "note": (
                "BGMI-VM obfuscation detected. Full source recovery requires "
                "reverse-engineering the VM opcode table — see recovery report."
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "input": str(input_path),
                "elapsed_ms": int((time.time() - t0) * 1000)}


def _extract_main_constants(
    data: bytes,
    header: Dict[str, Any],
    deadline: float | None = None,
) -> list:
    """Extract a bounded constant pool for BGMI diagnostics."""
    r = Reader(data, deadline=deadline)
    r.lua_int_size = header["lua_int_size"]
    r.lua_num_size = header["lua_num_size"]
    r._pos = header["main_offset"]
    constants = []
    try:
        r.string()
        r.int_(); r.int_()
        r.uint8(); r.uint8(); r.uint8()
        n_code = r.int_()
        if n_code < 0 or n_code > r.remaining() // 4:
            raise ValueError(f"invalid instruction count {n_code}")
        r._pos += n_code * 4
        n_const = r.int_()
        if n_const < 0 or n_const > r.remaining():
            raise ValueError(f"invalid constant count {n_const}")
        for index in range(n_const):
            if deadline is not None and (index & 0x3FF) == 0 and time.monotonic() >= deadline:
                raise TimeoutError("BGMI constant extraction deadline exceeded")
            t = r.uint8()
            if t == 0:
                constants.append(("nil", None))
            elif t == 1:
                constants.append(("bool", bool(r.uint8())))
            elif t == 3:
                constants.append(("flt", r.lua_num()))
            elif t == 19:
                constants.append(("int", r.lua_int()))
            elif t in (4, 20):
                constants.append(("str", r.string()))
            else:
                constants.append((f"unknown_{t}", None))
    except Exception:
        pass
    return constants


# ────────────────────────────────────────────────────────────────────────────
# Top-level dispatcher: try every known pattern
# ────────────────────────────────────────────────────────────────────────────

def vm_deobfuscate(input_path: Path, out_dir: Path) -> Dict[str, Any]:
    """Try every registered pattern; return the result of the best match.

    If no pattern matches, return ok=False with a diagnostic. If a pattern
    matches but its deobfuscator returns partial recovery, the result is
    forwarded honestly (no upgrade to 'full recovery').
    """
    from .pattern_registry import get_registry
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = get_registry()
    matches = registry.detect(input_path)
    if not matches:
        return {
            "ok": False,
            "recovered": False,
            "mode": "no_match",
            "input": str(input_path),
            "note": (
                "No known protection pattern matches this file. The standard "
                "decompile path (unluac + decompiler53) is the only remaining "
                "option. If this is a new protection scheme, add a Pattern "
                "entry to lua_engine/pattern_registry.py to extend ALVSIA."
            ),
        }
    # Try the highest-confidence match first
    best = max(matches, key=lambda p: p.confidence_boost)
    try:
        result = best.deobfuscator(input_path, out_dir)
        result["pattern_id"] = best.id
        result["pattern_label"] = best.label
        return result
    except Exception as exc:
        return {
            "ok": False,
            "recovered": False,
            "mode": "deobfuscator_exception",
            "pattern_id": best.id,
            "input": str(input_path),
            "error": f"{type(exc).__name__}: {exc}",
        }
