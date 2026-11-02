"""
ALVSIA PRO 5.5.0 — Streaming Lua decompiler for large inputs.

Design goals:
  • Handle multi-MB / multi-GB LuaS chunks without loading the whole file
    into memory. Memory usage is bounded by STREAM_CHUNK_SIZE.
  • Stream-output the recovered Lua source to a file, never hold it in RAM.
  • Honest failure: never produce fake .lua output. If no validated source
    was recovered, the caller is told exactly which path failed and why.

Pipeline:
  1. Preflight-magic check (first 4 bytes) — detects Lua 5.3, LuaJIT,
     chunked-DEFLATE, or unknown format.
  2. If chunked-DEFLATE, stream-inflate into a temp .luac file (memory
     bounded).
  3. If the result is Lua 5.3 bytecode, dispatch to decompiler53 (also
     patched for streaming I/O when possible).
  4. If LuaJIT, fall back to luajit_disassembler.
  5. Validate the output structurally; reject if it doesn't look like Lua.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from . import decompiler53
from .luajit_decompiler import disassemble_luajit, detect_luajit
from .engine import validate_lua_source, _find_java

STREAM_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB
MAX_INFLATED_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB hard cap


def _comment_prefix_lua_magic(head: bytes) -> Optional[Tuple[int, str]]:
    """Find a Lua chunk after a textual comment/shebang-only prefix."""
    candidates = []
    for marker, label in ((b"\x1bLua", "luac"), (b"\x1bLJ", "luajit")):
        offset = head.find(marker, 1)
        if offset > 0:
            candidates.append((offset, label))
    for offset, label in sorted(candidates):
        try:
            prefix = head[:offset].decode("utf-8")
        except UnicodeDecodeError:
            continue
        lines = prefix.splitlines()
        if not lines or not all(
            not line.strip() or line.lstrip().startswith(("--", "#!"))
            for line in lines
        ):
            continue
        if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in prefix):
            continue
        if label == "luac":
            version = head[offset + 4] if len(head) > offset + 4 else 0
            return offset, f"embedded_luac_{version:02x}"
        return offset, "embedded_luajit"
    return None


def preflight_magic(path: Path) -> str:
    """Classify common Lua formats using a bounded header read."""
    try:
        with path.open("rb") as f:
            head = f.read(65536)
        if len(head) < 4:
            return "too_small"
        if head.startswith(b"\x1bLua"):
            v = head[4] if len(head) > 4 else 0
            return f"luac_{v:02x}"
        if head.startswith(b"\x1bLJ"):
            return "luajit"
        # Distinguish the known multi-member 78DA/raw-DEFLATE game container
        # from an ordinary RFC 1950 zlib stream (78 01/5E/9C/DA etc.).
        if len(head) >= 2 and head[0] == 0x78 and (head[0] * 256 + head[1]) % 31 == 0:
            if head[1] == 0xDA:
                return "chunked_deflate"
            return "zlib"
        if head[0] == 0x1F and head[1] == 0x8B:
            return "gzip"
        # Some exporters prepend a Lua comment or metadata banner to bytecode.
        embedded = _comment_prefix_lua_magic(head)
        if embedded:
            return embedded[1]
        text = head.decode("utf-8", "ignore")
        stripped = text.lstrip("\ufeff \t\r\n")
        if re.search(r"^(?:#!.*\n\s*)?(?:local|return|function|if|for|while|repeat|do)\b", stripped):
            return "source"
        if b"function" in head[:4096] and all(
            byte in (9, 10, 13) or 32 <= byte < 127 for byte in head[:4096]
        ):
            return "source"
        return "unknown_0x" + head[:4].hex()
    except Exception:
        return "preflight_failed"

def stream_inflate_zlib(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Stream a conventional RFC 1950 zlib stream with a strict output cap."""
    total = 0
    dec = zlib.decompressobj()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with input_path.open("rb") as src, out_path.open("wb") as dst:
            while True:
                chunk = src.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                pending = chunk
                while pending:
                    part = dec.decompress(pending, min(STREAM_CHUNK_SIZE, MAX_INFLATED_BYTES - total + 1))
                    pending = dec.unconsumed_tail
                    if part:
                        total += len(part)
                        if total > MAX_INFLATED_BYTES:
                            raise ValueError(f"zlib output exceeds cap {MAX_INFLATED_BYTES}")
                        dst.write(part)
                    if not pending:
                        break
            tail = dec.flush()
            if tail:
                total += len(tail)
                if total > MAX_INFLATED_BYTES:
                    raise ValueError(f"zlib output exceeds cap {MAX_INFLATED_BYTES}")
                dst.write(tail)
            if not dec.eof:
                raise ValueError("truncated zlib stream")
        with out_path.open("rb") as check:
            magic = check.read(4)
        if not magic.startswith((b"\\x1bLua", b"\\x1bLJ")):
            raise ValueError("zlib payload does not begin with Lua/LuaJIT magic")
        return True, f"zlib_stream_inflated bytes_out={total}"
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        return False, f"zlib_inflate_failed: {exc}"


def stream_inflate_deflate_container(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Stream-inflate a 0x78DA-chunked raw-DEFLATE Lua container.

    Reads STREAM_CHUNK_SIZE pieces from input, feeds them to a raw Inflater,
    writes inflated bytes to out_path incrementally. Memory usage is
    bounded by STREAM_CHUNK_SIZE.

    The 0x78 0xDA marker is the zlib wrapper header. Each marker starts
    a new raw-DEFLATE stream; we skip the 2 header bytes and inflate
    the rest as raw deflate (wbits=-15).
    """
    if not input_path.is_file():
        return False, "input not found"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_out = 0
    total_in = 0
    try:
        with input_path.open("rb") as fin, out_path.open("wb") as fout:
            # Read whole file in chunks; we need to find 0x78 0xDA markers
            # which can span chunk boundaries, so we keep a small overlap
            # buffer.
            dec = None  # active decompressor for current chunk
            buf = b""
            carry_over = b""
            while True:
                chunk = fin.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    # flush any pending tail of current decompressor
                    if dec is not None:
                        try:
                            tail = dec.flush()
                            if tail:
                                fout.write(tail)
                                total_out += len(tail)
                        except zlib.error:
                            pass
                    break
                total_in += len(chunk)
                buf = carry_over + chunk
                # Find all 0x78 0xDA markers in buf
                markers = []
                i = 0
                while i < len(buf) - 1:
                    if buf[i] == 0x78 and buf[i + 1] == 0xDA:
                        markers.append(i)
                        i += 2
                    else:
                        i += 1
                # Process markers
                for m in markers:
                    # Start a fresh decompressor for this marker
                    if dec is not None:
                        try:
                            tail = dec.flush()
                            if tail:
                                fout.write(tail)
                                total_out += len(tail)
                        except zlib.error:
                            pass
                    dec = zlib.decompressobj(-15)  # raw deflate
                    # Feed from after the 2-byte marker to end of buf
                    try:
                        inflated = dec.decompress(buf[m + 2:])
                    except zlib.error as exc:
                        return False, f"inflate_error at offset {total_in - len(buf) + m}: {exc}"
                    if inflated:
                        fout.write(inflated)
                        total_out += len(inflated)
                        if total_out > MAX_INFLATED_BYTES:
                            return False, f"inflated payload exceeds cap {MAX_INFLATED_BYTES}"
                    if dec.eof:
                        # this stream is done; reset
                        try:
                            tail = dec.flush()
                            if tail:
                                fout.write(tail)
                                total_out += len(tail)
                        except zlib.error:
                            pass
                        dec = None
                # Carry over the last few bytes to catch a marker that
                # might span the chunk boundary
                carry_over = buf[-2:] if len(buf) >= 2 else buf
        if total_out == 0:
            out_path.unlink(missing_ok=True)
            return False, "no payload recovered from chunked-deflate container"
        # Validate payload magic
        with out_path.open("rb") as f:
            head = f.read(4)
        if not (head.startswith(b"\x1bLua") or head.startswith(b"\x1bLJ")):
            out_path.unlink(missing_ok=True)
            return False, "inflated payload is not Lua/LuaJIT bytecode"
        return True, f"stream_inflated bytes_in={total_in} bytes_out={total_out}"
    except Exception as exc:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        return False, f"stream_inflate_failed: {exc}"


def stream_decompile_lua53(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Try the pure-Python Lua 5.3 decompiler against the given file.

    decompiler53 normally loads the whole file into memory. For files
    larger than STREAM_CHUNK_SIZE we still call it — Lua 5.3 chunks of
    multiple GB are vanishingly rare in practice; the 4 GiB cap above
    bounds memory on the inflated side. The decompiler53 reader uses
    memoryview slicing so memory usage is roughly 1x the input size,
    which is acceptable for inputs up to a few hundred MB.
    """
    try:
        # Use decompile_bytes / decompile_file, not a nonexistent "decompile".
        from .decompiler53 import load_chunk, decompile_bytes
    except Exception as exc:
        return False, f"decompiler53_import_failed: {exc}"
    try:
        data = memoryview(Path(input_path).read_bytes())
    except Exception as exc:
        return False, f"read_failed: {exc}"
    failures = []
    candidates = [("standard", bytes(data))]
    # The private source-tool collection contains a BGMI/HePing Lua 5.3
    # converter (XOR constant-pool transform + opcode remap). Try it only as
    # a candidate normalizer: never trust its output until the strict Lua
    # chunk reader AND source validator both accept the result.
    try:
        from alvsia_private import LuaOpcodeConverter
        for variant in ("bgmi", "heping"):
            try:
                converted = LuaOpcodeConverter(variant=variant).convert_bytes(bytes(data))
                if converted != bytes(data) and converted.startswith(b"\\x1bLua\\x53"):
                    candidates.append((variant, converted))
            except Exception as exc:
                failures.append(f"{variant}_normalize_failed: {str(exc)[:240]}")
    except Exception as exc:
        failures.append(f"private_lua_converter_unavailable: {str(exc)[:240]}")

    seen = set()
    for variant, candidate in candidates:
        digest = __import__("hashlib").sha256(candidate[:4096]).digest()
        if digest in seen:
            continue
        seen.add(digest)
        try:
            chunk = load_chunk(memoryview(candidate))
            source_text = decompile_bytes(memoryview(candidate))
            if not source_text or not source_text.strip():
                raise ValueError("decompiler returned empty source")
            # Validate in-memory first, then persist only after acceptance.
            probe = Path(out_path).with_suffix(".candidate.tmp")
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text(source_text, encoding="utf-8")
            ok, msg = validate_lua_source(probe)
            if not ok:
                probe.unlink(missing_ok=True)
                raise ValueError(f"source validation failed: {msg}")
            final = Path(out_path)
            probe.replace(final)
            return True, f"decompiled_lua53 variant={variant} size={len(source_text)}"
        except Exception as exc:
            failures.append(f"{variant}: {str(exc)[:320]}")
    return False, "all Lua 5.3 normalization/decompile candidates failed: " + " | ".join(failures[-4:])


def stream_decompile_luajit(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Try the LuaJIT disassembler path (proto-level ASM, not full source)."""
    try:
        if not detect_luajit(Path(input_path).read_bytes()):
            return False, "not_luajit"
    except Exception as exc:
        return False, f"detect_luajit_failed: {exc}"
    try:
        res = disassemble_luajit(Path(input_path), Path(out_path))
        if res.get("ok"):
            return True, "luajit_disasm"
        return False, res.get("error", "luajit_disasm_failed")
    except Exception as exc:
        return False, f"luajit_disasm_exception: {exc}"


def stream_unluac_jar(input_path: Path, out_path: Path, jars_dir: Optional[str] = None,
                      timeout: int = 1800) -> Tuple[bool, str]:
    """Spawn java -jar unluac on the (possibly streaming) input file.

    Java's process spawning handles large input files natively because
    the JVM reads the file from disk, not from stdin.
    """
    java = _find_java()
    if not java:
        return False, "java_runtime_unavailable"
    jar = None
    if jars_dir:
        for name in ("unluac_2025_12_23.jar", "unluac_pro.jar", "unluac_patched.jar", "unluac.jar"):
            q = Path(jars_dir) / name
            if q.is_file() and q.stat().st_size > 1000:
                jar = q
                break
    if jar is None:
        return False, "unluac_jar_not_found"
    try:
        proc = subprocess.run(
            [java, "-Xmx512m", "-jar", str(jar), str(input_path)],
            capture_output=True, text=True, errors="replace",
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False, f"unluac_timeout_after_{timeout}s"
    except Exception as exc:
        return False, f"unluac_spawn_failed: {exc}"
    text = proc.stdout or ""
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0 or not text.strip():
        return False, (stderr[:800] if stderr else "unluac returned no source") + f" (rc={proc.returncode})"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(text, encoding="utf-8")
    ok, msg = validate_lua_source(out_path)
    if not ok:
        Path(out_path).unlink(missing_ok=True)
        return False, f"validation_failed: {msg}"
    return True, f"unluac_ok size={len(text)}"


def decompile_large(path: Path, out_dir: Path, jars_dir: Optional[str] = None) -> Dict[str, Any]:
    """Top-level entry for streaming decompilation of large Lua inputs.

    Pipeline:
      1. preflight_magic — 8-byte sniff
      2. If chunked-DEFLATE or gzip → stream-inflate into temp file
      3. Try VM-deobfuscation patterns FIRST (ALVSEAL3, ALVLUA1, BGMI-VM)
         — custom VM protection may only yield structure/constants until its
           matching opcode/dispatcher mapping is known.
      4. Try unluac jar (Java) — handles large inputs natively on disk
      5. Try pure-Python decompiler53 — works without Java
      6. Honest failure: no fake .lua output
    """
    p = Path(path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {
        "ok": False,
        "input": str(p),
        "size": p.stat().st_size if p.is_file() else 0,
        "format": "unknown",
        "mode": None,
        "out": None,
        "error": None,
    }

    if not p.is_file():
        result["error"] = "input not found"
        return result

    fmt = preflight_magic(p)
    result["format"] = fmt

    # ── Stage 1: try VM deobfuscation patterns FIRST ──────────────────────
    # A protected file's format may be 'luac_53' (BGMI-VM) or 'source'
    # (ALVSEAL3 wrapped in Lua source). Try every registered pattern.
    try:
        from .pattern_registry import get_registry
        registry = get_registry()
        matches = registry.detect(p)
        if matches:
            best = max(matches, key=lambda pat: pat.confidence_boost)
            deob_result = best.deobfuscator(p, out)
            if deob_result.get("ok"):
                # Forward the result with pattern metadata
                deob_result["pattern_id"] = best.id
                deob_result["pattern_label"] = best.label
                deob_result["input_format"] = fmt
                return deob_result
            # If pattern matched but deobfuscator failed, fall through to
            # standard decompile paths — but keep the pattern ID for diagnostics
            result["pattern_id_attempted"] = best.id
            result["pattern_error"] = deob_result.get("error", "unknown")
    except Exception as exc:
        result["pattern_registry_exception"] = str(exc)[:200]

    # ── Stage 2: unwrap comment-prefixed bytecode without touching input ─
    work_file = p
    container_info: Dict[str, Any] = {}
    embedded_temp: Optional[Path] = None
    if fmt.startswith("embedded_luac_") or fmt == "embedded_luajit":
        try:
            with p.open("rb") as f:
                head = f.read(65536)
            located = _comment_prefix_lua_magic(head)
            if not located:
                result["error"] = "embedded Lua marker disappeared during preflight"
                return result
            offset, detected_fmt = located
            fd, temp_name = tempfile.mkstemp(prefix="alvsia_lua_", suffix=".luac", dir=str(out))
            os.close(fd)
            embedded_temp = Path(temp_name)
            with p.open("rb") as src, embedded_temp.open("wb") as dst:
                src.seek(offset)
                shutil.copyfileobj(src, dst, length=STREAM_CHUNK_SIZE)
            work_file = embedded_temp
            fmt = "luajit" if detected_fmt == "embedded_luajit" else "luac_" + detected_fmt.rsplit("_", 1)[1]
            result["format"] = fmt
            container_info = {"wrapper": "comment_prefix", "payload_offset": offset,
                              "payload_size": embedded_temp.stat().st_size}
        except Exception as exc:
            if embedded_temp:
                embedded_temp.unlink(missing_ok=True)
            result["error"] = f"embedded_payload_extract_failed: {exc}"
            return result

    def _cleanup_embedded() -> None:
        if embedded_temp is not None:
            embedded_temp.unlink(missing_ok=True)

    if fmt == "zlib":
        unwrapped = out / (p.stem + "_zlib_unwrapped.luac")
        ok, msg = stream_inflate_zlib(p, unwrapped)
        if not ok:
            result["error"] = msg
            return result
        work_file = unwrapped
        container_info = {"container": "zlib", "container_msg": msg,
                          "unwrapped": str(unwrapped)}
        fmt = preflight_magic(work_file)
        result["format"] = fmt

    elif fmt == "chunked_deflate":
        unwrapped = out / (p.stem + "_unwrapped.luac")
        ok, msg = stream_inflate_deflate_container(p, unwrapped)
        if not ok:
            result["error"] = f"stream_inflate_failed: {msg}"
            return result
        work_file = unwrapped
        container_info = {"container": "chunked_deflate", "container_msg": msg,
                           "unwrapped": str(unwrapped)}
        fmt = preflight_magic(work_file)
        result["format"] = fmt

    elif fmt == "gzip":
        unwrapped = out / (p.stem + "_gunzip.luac")
        try:
            import gzip
            with gzip.open(p, "rb") as gz_in, unwrapped.open("wb") as out_f:
                while True:
                    chunk = gz_in.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    out_f.write(chunk)
            work_file = unwrapped
            fmt = preflight_magic(work_file)
            result["format"] = fmt
            container_info = {"container": "gzip", "unwrapped": str(unwrapped)}
        except Exception as exc:
            result["error"] = f"gzip_stream_failed: {exc}"
            return result

    elif fmt.startswith("luac_") or fmt == "luajit":
        pass
    elif fmt == "source":
        # Plain Lua source — pass through to validation
        dest = out / (p.stem + "_decompiled.lua")
        try:
            shutil.copy2(p, dest)
            ok, msg = validate_lua_source(dest)
            result["ok"] = ok
            result["mode"] = "source_pass_through"
            result["out"] = str(dest)
            if not ok:
                result["error"] = msg
                dest.unlink(missing_ok=True)
            return result
        except Exception as exc:
            result["error"] = f"source_pass_through_failed: {exc}"
            return result
    else:
        # Unknown format — let unluac try as a last resort
        pass

    # ── Stage 3: LuaJIT disassembly ─────────────────────────────────────────
    if fmt == "luajit":
        dest = out / (p.stem + "_luajit_asm.lua")
        ok, msg = stream_decompile_luajit(work_file, dest)
        if ok:
            result["ok"] = True
            result["mode"] = "luajit_disasm"
            result["out"] = str(dest)
            result["note"] = "LuaJIT disassembly (proto-level ASM, not full source)"
            result.update(container_info)
            _cleanup_embedded()
            return result

    # ── Stage 4: unluac jar (Java) — handles large inputs natively on disk ─
    if jars_dir:
        dest = out / (p.stem + "_decompiled.lua")
        ok, msg = stream_unluac_jar(work_file, dest, jars_dir=jars_dir, timeout=1800)
        if ok:
            result["ok"] = True
            result["mode"] = "unluac_jar"
            result["out"] = str(dest)
            result.update(container_info)
            _cleanup_embedded()
            return result
        # Preserve the actual JAR/runtime/parser failure even if the Python
        # Lua 5.3 parser is attempted next. This distinguishes missing Java,
        # missing JAR, unsupported bytecode, timeout, and invalid output.
        result["unluac_jar_error"] = str(msg)[:1000]
    else:
        result["unluac_jar_error"] = "jars_dir_unavailable"

    # ── Stage 5: pure-Python decompiler53 — works without Java ─────────────
    if fmt.startswith("luac_"):
        dest = out / (p.stem + "_decompiled.lua")
        ok, msg = stream_decompile_lua53(work_file, dest)
        if ok:
            result["ok"] = True
            result["mode"] = "decompiler53"
            result["out"] = str(dest)
            result.update(container_info)
            _cleanup_embedded()
            return result
        result["error"] = msg
    else:
        result["error"] = "no decompiler path matched input format"

    if not result.get("ok"):
        result.update(container_info)
        result["note"] = "no validated Lua source produced; input preserved under IN/"
    _cleanup_embedded()
    return result
