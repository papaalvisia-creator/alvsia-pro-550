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


if __name__ == "__main__":
    import sys
    p = Path(sys.argv[1])
    o = Path(sys.argv[2]) if len(sys.argv) > 2 else p.parent / "recover_out"
    print(recover_strings(p.read_bytes(), o, p.stem))
