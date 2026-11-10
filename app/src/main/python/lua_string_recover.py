# -*- coding: utf-8 -*-
"""Deterministic string recovery for LuaS / binary containers.

This module deliberately separates candidate generation from ranking.  It never
claims that a printable XOR candidate is a successful decryption; candidates
are reported with their score and transform metadata.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

COMMON_XOR_KEYS = list(range(1, 32)) + [0x18, 0x5A, 0xAA, 0xFF, 0x33, 0x55, 0x7F]
MULTI_KEYS = [
    b"PUBG", b"Tencent", b"igame", b"slua", b"LuaS", b"BGMI",
    b"\x18\x18\x18\x18", b"\xaa\x55\xaa\x55",
]
DEFAULT_MAX_OUTPUT_LINES = 20_000
DEFAULT_SAMPLE_LIMIT = 6_000_000


def _printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    ok = sum(1 for x in data if 32 <= x < 127 or x in (9, 10, 13))
    return ok / len(data)


def _extract_ascii(data: bytes, min_len: int = 4, max_lines: int | None = None) -> list[str]:
    out: list[str] = []
    cur = bytearray()
    for x in data:
        if 32 <= x < 127:
            cur.append(x)
        else:
            if len(cur) >= min_len:
                out.append(cur.decode("ascii", "ignore"))
                if max_lines is not None and len(out) >= max_lines:
                    return out
            cur.clear()
    if len(cur) >= min_len and (max_lines is None or len(out) < max_lines):
        out.append(cur.decode("ascii", "ignore"))
    return out


def _xor_single(data: bytes, key: int) -> bytes:
    if not 0 <= key <= 255:
        raise ValueError("XOR key must be in 0..255")
    return bytes(b ^ key for b in data)


def _xor_multi(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("XOR key must not be empty")
    return bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))


def _candidate_score(strings: Iterable[str], decoded: bytes) -> tuple[float, int, int]:
    strings = list(strings)
    alpha_hits = sum(1 for s in strings if re.search(r"[A-Za-z]{4,}", s))
    keyword_hits = sum(
        s.lower().count(k)
        for s in strings
        for k in ("function", "character", "player", "require", "local", "server", "rpc", "self")
    )
    return (_printable_ratio(decoded), alpha_hits, keyword_hits)


def rank_xor_candidates(
    data: bytes,
    keys: Iterable[int] = COMMON_XOR_KEYS,
    *,
    min_len: int = 6,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> list[dict]:
    """Return deterministic, evidence-based single-byte XOR candidates."""
    sample = data if len(data) <= sample_limit else data[: sample_limit // 2] + data[-sample_limit // 2 :]
    ranked = []
    for key in sorted(set(keys)):
        decoded = _xor_single(sample, key)
        strings = _extract_ascii(decoded, min_len=min_len, max_lines=DEFAULT_MAX_OUTPUT_LINES)
        ratio, alpha_hits, keyword_hits = _candidate_score(strings, decoded)
        ranked.append({
            "key": key,
            "key_hex": f"{key:02x}",
            "printable_ratio": round(ratio, 6),
            "alpha_hits": alpha_hits,
            "keyword_hits": keyword_hits,
            "string_count": len(strings),
        })
    ranked.sort(key=lambda x: (-x["keyword_hits"], -x["alpha_hits"], -x["printable_ratio"], x["key"]))
    return ranked


def recover_strings(data: bytes, out_dir: Path, stem: str = "lua") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"steps": [], "best_key": None, "best_count": 0, "candidate_count": 0}

    plain = _extract_ascii(data, max_lines=DEFAULT_MAX_OUTPUT_LINES)
    (out_dir / f"{stem}_strings_plain.txt").write_text("\n".join(plain), encoding="utf-8")
    report["steps"].append({"mode": "plain", "count": len(plain)})

    ranked = rank_xor_candidates(data)
    report["candidate_count"] = len(ranked)
    best = ranked[0] if ranked else None
    if best and (best["alpha_hits"] > 0 or best["printable_ratio"] >= 0.70):
        key = best["key"]
        decoded = _xor_single(data if len(data) <= 12_000_000 else data[:DEFAULT_SAMPLE_LIMIT], key)
        strings = _extract_ascii(decoded, min_len=5, max_lines=DEFAULT_MAX_OUTPUT_LINES)
        (out_dir / f"{stem}_strings_xor_{key:02x}.txt").write_text("\n".join(strings), encoding="utf-8")
        report["steps"].append({"mode": "xor_single", **best, "count": len(strings)})
        report["best_key"] = f"xor_{key:02x}"
        report["best_count"] = len(strings)

    sample = data if len(data) <= DEFAULT_SAMPLE_LIMIT else data[:DEFAULT_SAMPLE_LIMIT]
    for mk in MULTI_KEYS:
        decoded = _xor_multi(sample, mk)
        strings = _extract_ascii(decoded, min_len=6, max_lines=8_000)
        ratio, alpha_hits, keyword_hits = _candidate_score(strings, decoded)
        if keyword_hits > 0 or (alpha_hits > 20 and ratio >= 0.45):
            name = mk.hex()
            (out_dir / f"{stem}_strings_mxor_{name}.txt").write_text("\n".join(strings), encoding="utf-8")
            report["steps"].append({
                "mode": "xor_multi", "key_hex": name, "printable_ratio": round(ratio, 6),
                "alpha_hits": alpha_hits, "keyword_hits": keyword_hits, "count": len(strings),
            })

    found = {}
    for p in out_dir.glob(f"{stem}_strings_*.txt"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        for kw in ("function", "Character", "Player", "require", "local", "Server", "RPC", "self"):
            c = t.count(kw)
            if c:
                found[kw] = found.get(kw, 0) + c
    report["keyword_hits"] = found
    (out_dir / f"{stem}_RECOVERY_REPORT.txt").write_text(
        repr(report), encoding="utf-8"
    )
    return report


def _iter_ascii_file(path: Path, *, min_len: int = 4, xor_key: int | None = None,
                     xor_multi_key: bytes | None = None, chunk_size: int = 1024 * 1024,
                     max_run: int = 1024 * 1024):
    """Yield printable runs using bounded chunks and C-level byte scanning.

    Only the unfinished printable suffix is carried between reads. Long runs
    are emitted in bounded pieces, so even multi-GB inputs cannot grow a
    Python bytearray in proportion to the input size.
    """
    if chunk_size <= 0 or max_run <= 0 or min_len <= 0:
        raise ValueError("chunk_size, max_run and min_len must be positive")
    if xor_multi_key is not None and not xor_multi_key:
        raise ValueError("multi-byte XOR key must not be empty")

    printable_runs = re.compile(rb"[ -~]+")
    offset = 0
    pending = b""
    with Path(path).open("rb") as source:
        while True:
            block = source.read(chunk_size)
            eof = not block
            if not eof:
                if xor_key is not None:
                    if not 0 <= xor_key <= 255:
                        raise ValueError("XOR key must be in 0..255")
                    block = bytes(value ^ xor_key for value in block)
                elif xor_multi_key is not None:
                    key_len = len(xor_multi_key)
                    block = bytes(value ^ xor_multi_key[(offset + i) % key_len]
                                  for i, value in enumerate(block))
                offset += len(block)

            data = pending + block
            pending = b""
            for match in printable_runs.finditer(data):
                run = match.group()
                is_unfinished_tail = not eof and match.end() == len(data)
                if is_unfinished_tail:
                    while len(run) > max_run:
                        piece, run = run[:max_run], run[max_run:]
                        if len(piece) >= min_len:
                            yield piece.decode("ascii")
                    pending = run
                    continue
                for start in range(0, len(run), max_run):
                    piece = run[start:start + max_run]
                    if len(piece) >= min_len:
                        yield piece.decode("ascii")

            if eof:
                break
    if len(pending) >= min_len:
        yield pending.decode("ascii")


def _write_stream_strings(path: Path, source: Path, *, min_len: int = 4,
                          xor_key: int | None = None, xor_multi_key: bytes | None = None,
                          max_lines: int = DEFAULT_MAX_OUTPUT_LINES) -> int:
    count = 0
    with Path(path).open("w", encoding="utf-8") as target:
        for value in _iter_ascii_file(source, min_len=min_len, xor_key=xor_key,
                                      xor_multi_key=xor_multi_key):
            target.write(value + "\n")
            count += 1
            if count >= max_lines:
                break
    return count


def recover_strings_file(input_path: Path, out_dir: Path, stem: str = "lua") -> dict:
    """Recover strings from very large inputs with bounded RAM usage."""
    source = Path(input_path)
    if not source.is_file():
        return {"ok": False, "error": "input file not found"}
    size = source.stat().st_size
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"steps": [], "best_key": None, "best_count": 0, "candidate_count": 0,
              "input_bytes": size, "streaming": True}

    plain_path = out_dir / f"{stem}_strings_plain.txt"
    plain_count = _write_stream_strings(plain_path, source, max_lines=DEFAULT_MAX_OUTPUT_LINES)
    report["steps"].append({"mode": "plain", "count": plain_count, "out": str(plain_path)})

    with source.open("rb") as handle:
        if size <= DEFAULT_SAMPLE_LIMIT:
            sample = handle.read(DEFAULT_SAMPLE_LIMIT)
        else:
            head_size = DEFAULT_SAMPLE_LIMIT // 2
            head = handle.read(head_size)
            handle.seek(max(0, size - (DEFAULT_SAMPLE_LIMIT - head_size)))
            tail = handle.read(DEFAULT_SAMPLE_LIMIT - head_size)
            sample = head + tail

    ranked = rank_xor_candidates(sample)
    report["candidate_count"] = len(ranked)
    best = ranked[0] if ranked else None
    if best and (best["alpha_hits"] > 0 or best["printable_ratio"] >= 0.70):
        key = best["key"]
        output = out_dir / f"{stem}_strings_xor_{key:02x}.txt"
        count = _write_stream_strings(output, source, min_len=5, xor_key=key,
                                      max_lines=DEFAULT_MAX_OUTPUT_LINES)
        report["steps"].append({"mode": "xor_single", **best, "count": count,
                                "out": str(output)})
        report["best_key"] = f"xor_{key:02x}"
        report["best_count"] = count

    # Multi-key ranking uses a bounded representative sample; no GB-sized
    # decoded copy is ever materialized.
    head_sample = sample[:DEFAULT_SAMPLE_LIMIT]
    for multi_key in MULTI_KEYS:
        decoded = _xor_multi(head_sample, multi_key)
        strings = _extract_ascii(decoded, min_len=6, max_lines=8_000)
        ratio, alpha_hits, keyword_hits = _candidate_score(strings, decoded)
        if keyword_hits > 0 or (alpha_hits > 20 and ratio >= 0.45):
            name = multi_key.hex()
            output = out_dir / f"{stem}_strings_mxor_{name}.txt"
            output.write_text("\n".join(strings), encoding="utf-8")
            report["steps"].append({"mode": "xor_multi", "key_hex": name,
                                    "printable_ratio": round(ratio, 6),
                                    "alpha_hits": alpha_hits, "keyword_hits": keyword_hits,
                                    "count": len(strings), "sample_bytes": len(head_sample),
                                    "out": str(output)})

    found = {}
    for output in out_dir.glob(f"{stem}_strings_*.txt"):
        with output.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                lowered = line.lower()
                for keyword in ("function", "character", "player", "require", "local", "server", "rpc", "self"):
                    count = lowered.count(keyword)
                    if count:
                        found[keyword] = found.get(keyword, 0) + count
    report["keyword_hits"] = found
    (out_dir / f"{stem}_RECOVERY_REPORT.txt").write_text(repr(report), encoding="utf-8")
    return {"ok": True, **report}


if __name__ == "__main__":
    import sys
    p = Path(sys.argv[1])
    o = Path(sys.argv[2]) if len(sys.argv) > 2 else p.parent / "recover_out"
    print(recover_strings_file(p, o, p.stem))
