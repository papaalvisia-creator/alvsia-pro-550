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
            # 78 DA is shared by RFC1950 zlib level-9 and the legacy
            # chunked raw-DEFLATE container. Probe standard zlib first;
            # accept it only when the inflated prefix is Lua bytecode.
            try:
                probe = zlib.decompressobj()
                inflated = probe.decompress(head, 64)
                if inflated.startswith((bytes((0x1B,)) + b"Lua", bytes((0x1B,)) + b"LJ")):
                    return "zlib"
            except zlib.error:
                pass
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
        if not magic.startswith((b"\x1bLua", b"\x1bLJ")):
            raise ValueError("zlib payload does not begin with Lua/LuaJIT magic")
        return True, f"zlib_stream_inflated bytes_out={total}"
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        return False, f"zlib_inflate_failed: {exc}"


def stream_inflate_deflate_container(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Stream-inflate concatenated 0x78DA/raw-DEFLATE members.

    A 0x78DA byte pair can also occur inside compressed payload data. It is
    therefore only a candidate marker: a member boundary is accepted only
    after the raw DEFLATE decoder reaches EOF. Inter-member separator bytes
    and false marker candidates are skipped without losing later valid data.
    """
    if not input_path.is_file():
        return False, "input not found"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_out = 0
    total_in = input_path.stat().st_size
    members = 0
    false_candidates = 0
    marker = b"\x78\xDA"

    def find_marker(fin, start_at: int) -> int:
        fin.seek(max(0, start_at))
        overlap = b""
        absolute = fin.tell()
        while True:
            block = fin.read(STREAM_CHUNK_SIZE)
            if not block:
                return -1
            data = overlap + block
            found = data.find(marker)
            if found >= 0:
                return absolute - len(overlap) + found
            overlap = data[-1:]
            absolute += len(block)

    out_path.unlink(missing_ok=True)
    try:
        with input_path.open("rb") as fin, out_path.open("wb") as fout:
            candidate = find_marker(fin, 0)
            while candidate >= 0:
                candidate_out = 0
                stream_end = -1
                valid = False
                failed = False
                dec = zlib.decompressobj(-15)
                with tempfile.TemporaryFile() as spool:
                    fin.seek(candidate + 2)
                    while True:
                        chunk_start = fin.tell()
                        chunk = fin.read(STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        pending = chunk
                        try:
                            while pending:
                                remaining = MAX_INFLATED_BYTES - total_out - candidate_out
                                if remaining < 0:
                                    raise ValueError(
                                        f"inflated payload exceeds cap {MAX_INFLATED_BYTES}"
                                    )
                                part = dec.decompress(
                                    pending, min(STREAM_CHUNK_SIZE, remaining + 1)
                                )
                                pending = dec.unconsumed_tail
                                if part:
                                    candidate_out += len(part)
                                    if candidate_out + total_out > MAX_INFLATED_BYTES:
                                        raise ValueError(
                                            f"inflated payload exceeds cap {MAX_INFLATED_BYTES}"
                                        )
                                    spool.write(part)
                                if dec.eof:
                                    stream_end = chunk_start + len(chunk) - len(dec.unused_data)
                                    valid = candidate_out > 0
                                    break
                                if not pending:
                                    break
                        except zlib.error:
                            failed = True
                        if valid or failed:
                            break
                    if valid and stream_end >= 0:
                        spool.seek(0)
                        while True:
                            part = spool.read(STREAM_CHUNK_SIZE)
                            if not part:
                                break
                            fout.write(part)
                        total_out += candidate_out
                        members += 1
                        candidate = find_marker(fin, stream_end)
                    else:
                        false_candidates += 1
                        candidate = find_marker(fin, candidate + 2)
            fout.flush()
        if total_out == 0:
            out_path.unlink(missing_ok=True)
            return False, "no valid raw-DEFLATE members recovered"
        with out_path.open("rb") as f:
            head = f.read(4)
        if not (head.startswith(b"\x1bLua") or head.startswith(b"\x1bLJ")):
            out_path.unlink(missing_ok=True)
            return False, "inflated payload is not Lua/LuaJIT bytecode"
        return True, (
            f"stream_inflated bytes_in={total_in} bytes_out={total_out} "
            f"members={members} skipped_marker_candidates={false_candidates}"
        )
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        return False, f"stream_inflate_failed: {exc}"

def stream_decompile_lua53(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Run the Lua 5.3 recovery candidates under one cooperative wall-clock budget."""
    try:
        from .decompiler53 import decompile_bytes
    except Exception as exc:
        return False, f"decompiler53_import_failed: {exc}"
    input_size = Path(input_path).stat().st_size
    max_parser_bytes = int(os.environ.get(
        "ALVSIA_LUA53_MAX_IN_MEMORY_BYTES", str(256 * 1024 * 1024)
    ))
    max_parser_bytes = max(16 * 1024 * 1024, min(max_parser_bytes, 512 * 1024 * 1024))
    if input_size > max_parser_bytes:
        return False, (
            f"lua53_parser_memory_limit: input={input_size} bytes "
            f"limit={max_parser_bytes} bytes; streaming container analysis remains available"
        )
    default_budget = "75" if os.environ.get("ALVSIA_SEALED_RUNTIME") == "1" else "120"
    try:
        budget_seconds = float(os.environ.get("ALVSIA_LUA53_TIMEOUT_SECONDS", default_budget))
    except (TypeError, ValueError):
        budget_seconds = float(default_budget)
    budget_seconds = max(10.0, min(budget_seconds, 180.0))
    deadline = __import__("time").monotonic() + budget_seconds
    try:
        data = Path(input_path).read_bytes()
    except Exception as exc:
        return False, f"read_failed: {exc}"

    failures = []
    seen = set()

    def _try_candidate(variant: str, candidate: bytes):
        if __import__("time").monotonic() >= deadline:
            return False, f"lua53_total_budget_exceeded_after_{budget_seconds:g}s"
        digest = __import__("hashlib").sha256(candidate).digest()
        if digest in seen:
            return False, "duplicate candidate"
        seen.add(digest)
        try:
            # decompile_bytes already performs strict chunk parsing; the old
            # extra load_chunk call parsed the complete bytecode twice.
            source_text = decompile_bytes(memoryview(candidate), deadline=deadline)
            if not source_text or not source_text.strip():
                raise ValueError("decompiler returned empty source")
            ok, msg = validate_lua_source(source_text, expected_version="Lua 5.3")
            if not ok:
                raise ValueError(f"source validation failed: {msg}")
            final = Path(out_path)
            final.parent.mkdir(parents=True, exist_ok=True)
            final.write_text(source_text, encoding="utf-8")
            return True, f"decompiled_lua53 variant={variant} size={len(source_text)}"
        except TimeoutError as exc:
            return False, f"lua53_total_budget_exceeded_after_{budget_seconds:g}s: {exc}"
        except Exception as exc:
            return False, f"{variant}: {str(exc)[:320]}"

    ok, note = _try_candidate("standard", data)
    if ok:
        return True, note
    failures.append(note)
    del data
    if note.startswith("lua53_total_budget_exceeded"):
        return False, note
    if __import__("time").monotonic() >= deadline:
        return False, "all Lua 5.3 candidates stopped: total parser time budget exceeded"

    # Existing BGMI/HePing normalizers remain enabled, but share the same
    # total deadline so a failed standard candidate cannot trigger an
    # unbounded chain of additional parser attempts.
    try:
        import gc
        from alvsia_private import LuaOpcodeConverter
        for variant in ("bgmi", "heping"):
            if __import__("time").monotonic() >= deadline:
                failures.append("remaining normalization candidates skipped: total time budget exhausted")
                break
            try:
                original = Path(input_path).read_bytes()
                converted = LuaOpcodeConverter(variant=variant).convert_bytes(original)
                del original
                if __import__("time").monotonic() >= deadline:
                    del converted
                    gc.collect()
                    failures.append(f"{variant}: total parser time budget exceeded during normalization")
                    break
                if converted == b"" or not converted.startswith(bytes((0x1B,)) + b"Lua" + bytes((0x53,))):
                    failures.append(f"{variant}: normalizer produced no Lua 5.3 candidate")
                    del converted
                    gc.collect()
                    continue
                ok, note = _try_candidate(variant, converted)
                if ok:
                    return True, note
                failures.append(note)
                del converted
                gc.collect()
                if __import__("time").monotonic() >= deadline:
                    break
            except Exception as exc:
                failures.append(f"{variant}_normalize_failed: {str(exc)[:240]}")
    except Exception as exc:
        failures.append(f"private_lua_converter_unavailable: {str(exc)[:240]}")

    return False, "all Lua 5.3 normalization/decompile candidates failed: " + " | ".join(failures[-4:])

def stream_decompile_luajit(input_path: Path, out_path: Path) -> Tuple[bool, str]:
    """Try the LuaJIT disassembler path (proto-level ASM, not full source)."""
    try:
        with Path(input_path).open("rb") as source:
            header = source.read(4)
        if not header.startswith(b"\\x1bLJ"):
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
    """Spawn java -jar unluac with bounded Android memory and wall-clock use.

    Desktop diagnostics retain the historical defaults. In the sealed Android
    runtime, cap the child JVM and timeout to avoid the app + parser exhausting
    device memory while other compatible engines remain available as fallback.
    """
    android_mode = os.environ.get("ALVSIA_SEALED_RUNTIME") == "1"
    # Android safety: keep Unluac available, but bound the child JVM heap so
    # Chaquopy + the app UI + the parser do not compete for an unbounded heap.
    # This is a resource guard, NOT an engine disable: Unluac remains a real
    # fallback and reports a normal parser/resource failure when its bound is
    # insufficient, allowing the remaining registered engines to continue.
    effective_timeout = min(timeout, 120) if android_mode else timeout
    heap_limit = os.environ.get(
        "ALVSIA_UNLUAC_JAVA_HEAP", "96m" if android_mode else "512m"
    )
    if not re.fullmatch(r"[1-9][0-9]{1,3}m", heap_limit):
        heap_limit = "96m" if android_mode else "512m"
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
            [java, f"-Xmx{heap_limit}", "-jar", str(jar), str(input_path)],
            capture_output=True, text=True, errors="replace",
            timeout=effective_timeout
        )
    except subprocess.TimeoutExpired:
        return False, f"unluac_timeout_after_{effective_timeout}s"
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


def probe_lua_header(path: Path) -> Dict[str, Any]:
    """Return bounded, non-destructive diagnostics for a failed Lua parse."""
    p = Path(path)
    result: Dict[str, Any] = {"size": p.stat().st_size if p.is_file() else 0}
    if not p.is_file():
        result["error"] = "input_not_found"
        return result
    with p.open("rb") as src:
        head = src.read(4096)
        src.seek(0)
        replacement_count = 0
        while True:
            block = src.read(STREAM_CHUNK_SIZE)
            if not block:
                break
            replacement_count += block.count(bytes((0xEF, 0xBF, 0xBD)))
    magic_offset = head.find(bytes((0x1B,)) + b"Lua")
    result["magic_offset"] = magic_offset if magic_offset >= 0 else None
    result["luajit_offset"] = head.find(bytes((0x1B,)) + b"LJ")
    result["first_48_hex"] = head[:48].hex()
    result["utf8_replacement_markers"] = replacement_count
    if magic_offset >= 0:
        chunk = head[magic_offset:]
        result["version"] = chunk[4] if len(chunk) > 4 else None
        result["format_byte"] = chunk[5] if len(chunk) > 5 else None
        result["luac_data_ok"] = len(chunk) >= 12 and chunk[6:12] == bytes((0x19,0x93,0x0D,0x0A,0x1A,0x0A))
        result["field_sizes"] = list(chunk[12:17]) if len(chunk) >= 17 else []
        result["header_complete"] = len(chunk) >= 33
    return result

def decompile_large(path: Path, out_dir: Path, jars_dir: Optional[str] = None, preflight_only: bool = False) -> Dict[str, Any]:
    """Top-level entry for streaming decompilation of large Lua inputs.

    Pipeline:
      1. preflight_magic — 8-byte sniff
      2. Try VM-deobfuscation patterns (ALVSEAL3, ALVLUA1, BGMI-VM)
      3. In normal mode, unwrap supported containers and run legacy engines.
      4. With preflight_only=True, return after pattern triage; the Smart Lua
         orchestrator owns all standard engine attempts and output selection.
      5. Honest failure: no fake .lua output.
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
        # Run only detectors compatible with the bounded header preflight.
        # In particular, never parse every Lua 5.3 proto tree for an ordinary
        # multi-megabyte source file just to discover that it is not BGMI VM.
        eligible_ids = {
            "source": {"ALVSEAL3_SOURCE"},
            "luac_53": {"BGMI_VM"},
        }.get(fmt, {"ALVLUA1_PAYLOAD"} if fmt.startswith("unknown_") else set())
        matches = []
        if hasattr(registry, "all_patterns"):
            for pattern in registry.all_patterns():
                if pattern.id not in eligible_ids:
                    continue
                try:
                    if pattern.detector(p):
                        matches.append(pattern)
                except Exception:
                    continue
        else:
            # Compatibility for third-party/test registries implementing the
            # original detect(path) protocol.
            matches = registry.detect(p)
        matches.sort(key=lambda pat: pat.confidence_boost, reverse=True)
        pattern_attempts = []
        for pattern in matches:
            try:
                deob_result = pattern.deobfuscator(p, out)
            except Exception as pattern_exc:
                deob_result = {"ok": False, "error": str(pattern_exc)}
            # "ok" can mean that a protection structure was inspected, not
            # that original source was recovered (BGMI_VM is intentionally
            # partial). Accept only an explicitly recovered, existing .lua
            # artifact that passes the common source validator.
            artifact = Path(str(deob_result.get("out") or ""))
            artifact_error = None
            if deob_result.get("ok") and deob_result.get("recovered") is True:
                try:
                    resolved_out = out.resolve()
                    resolved_artifact = artifact.resolve()
                    if resolved_out not in resolved_artifact.parents:
                        artifact_error = "recovered artifact is outside output directory"
                    elif not artifact.is_file() or artifact.suffix.lower() != ".lua":
                        artifact_error = "handler did not produce a .lua source artifact"
                    else:
                        valid, validation_message = validate_lua_source(artifact)
                        if not valid:
                            artifact_error = "source validation failed: " + validation_message
                except Exception as validation_exc:
                    artifact_error = "artifact validation exception: " + str(validation_exc)[:240]
            elif deob_result.get("ok"):
                artifact_error = "handler reported partial analysis, not full source recovery"
            else:
                artifact_error = str(deob_result.get("error", "unknown"))

            if deob_result.get("recovered") is False:
                result["recovered"] = False
                result["mode"] = deob_result.get("mode") or "protected_partial"
                result["pattern_id"] = pattern.id
                result["pattern_label"] = pattern.label
                for key in (
                    "protos_parsed", "main_code_count", "main_const_count",
                    "main_nested_count", "parse_errors", "structure_out",
                    "constants_out", "report_out", "note",
                ):
                    if key in deob_result:
                        result[key] = deob_result[key]

            if deob_result.get("ok") and deob_result.get("recovered") is True and artifact_error is None:
                deob_result["pattern_id"] = pattern.id
                deob_result["pattern_label"] = pattern.label
                deob_result["input_format"] = fmt
                deob_result["pattern_attempts"] = pattern_attempts + [
                    {"id": pattern.id, "ok": True, "recovered": True}
                ]
                return deob_result

            # Never surface a partial structure/constants dump as a successful
            # decompile. Remove an invalid .lua artifact so it cannot be
            # mistaken for recovered source; diagnostic reports remain intact.
            if artifact_error and artifact.suffix.lower() == ".lua":
                try:
                    resolved_out = out.resolve()
                    resolved_artifact = artifact.resolve()
                    if resolved_out in resolved_artifact.parents and artifact.is_file():
                        artifact.unlink()
                except Exception:
                    pass
            pattern_attempts.append({
                "id": pattern.id,
                "ok": False,
                "error": (artifact_error or "source recovery not validated")[:500],
            })
        if pattern_attempts:
            result["pattern_ids_attempted"] = [item["id"] for item in pattern_attempts]
            # Retain the legacy singular diagnostic fields for the bridge/UI.
            result["pattern_id_attempted"] = pattern_attempts[0]["id"]
            result["pattern_error"] = " | ".join(
                "%s: %s" % (item["id"], item["error"])
                for item in pattern_attempts
            )[:1000]
    except Exception as exc:
        result["pattern_registry_exception"] = str(exc)[:200]

    # Smart Lua asks this function for protection-pattern triage only. Standard
    # decompilation is owned by lua_engine.orchestrator so engines are not run
    # twice or allowed to short-circuit the shared selection/validation path.
    if preflight_only:
        if not result.get("mode"):
            result["mode"] = "pattern_preflight"
        return result

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
        # Disassembly is useful recovery evidence, but it is not reconstructed
        # Lua source. Never give an ASM listing a .lua extension or let callers
        # mistake it for a successful source decompilation.
        dest = out / (p.stem + "_luajit_disassembly.asm.txt")
        ok, msg = stream_decompile_luajit(work_file, dest)
        if ok:
            result["ok"] = False
            result["analysis_ok"] = True
            result["mode"] = "luajit_disasm"
            result["out"] = str(dest)
            result["artifact_kind"] = "disassembly"
            result["source_recovered"] = False
            result["note"] = "LuaJIT disassembly only; original Lua source was not reconstructed"
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
    if fmt == "luac_53":
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
        # Preserve byte-level evidence for custom headers or lossy text conversion.
        try:
            result["header_probe"] = probe_lua_header(work_file)
        except Exception as probe_exc:
            result["header_probe_error"] = str(probe_exc)[:160]
    elif fmt.startswith("luac_"):
        result["error"] = (
            "no Python decompiler for this Lua bytecode version; "
            "the compatible Unluac JAR backend was unavailable or failed"
        )
    else:
        result["error"] = "no decompiler path matched input format"

    if not result.get("ok"):
        result.update(container_info)
        result["note"] = "no validated Lua source produced; input preserved under IN/"
    _cleanup_embedded()
    return result
