# -*- coding: utf-8 -*-
"""Read-only reference inspection helpers for ALVSIA PRO.

Never executes inspected input, attaches to processes, or modifies source files.
Compatible with the Chaquopy Python 3.8 runtime.
"""
from __future__ import annotations
import hashlib
import math
import re
from pathlib import Path

def _entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    size = float(len(data))
    return -sum((n / size) * math.log(n / size, 2) for n in counts if n)

def probe_lua_file(path):
    """Identify common Lua/LuaJIT signatures without attempting decompilation."""
    p = Path(path)
    if p.stat().st_size > 16777216:
        raise ValueError("Lua probe input exceeds 16 MiB safety limit")
    raw = p.read_bytes()
    entropy = _entropy(raw[:min(len(raw), 262144)])
    result = {"file": p.name, "size": len(raw),
              "sha256": hashlib.sha256(raw).hexdigest(),
              "entropy": round(entropy, 3), "format": "unknown",
              "confidence": "low", "details": []}
    if raw.startswith(b"\x1bLua") and len(raw) >= 6:
        version = raw[4]
        names = {0x51: "Lua 5.1", 0x52: "Lua 5.2",
                 0x53: "Lua 5.3", 0x54: "Lua 5.4"}
        result["format"] = names.get(version, "Lua bytecode (unknown version)")
        result["confidence"] = "high" if version in names else "medium"
        if version not in names:
            result["details"].append("version_byte=0x%02X" % version)
    elif raw.startswith(b"\x1bLJ"):
        result["format"] = "LuaJIT bytecode"
        result["confidence"] = "high"
    elif raw.lstrip().startswith((b"local ", b"function ", b"return ", b"--", b"#!/")):
        result["format"] = "probable Lua source"
        result["confidence"] = "medium"
    elif raw.startswith(b"PK\x03\x04"):
        result["format"] = "ZIP/container (not raw Lua bytecode)"
        result["confidence"] = "high"
    elif raw.startswith(b"\x1f\x8b"):
        result["format"] = "gzip container"
        result["confidence"] = "high"
    elif raw.startswith((b"\x78\x01", b"\x78\x9c", b"\x78\xda")):
        result["format"] = "possible zlib container"
        result["confidence"] = "medium"
    else:
        result["details"].append("header=" + raw[:16].hex())
        if entropy >= 7.5:
            result["details"].append("high entropy: encrypted/compressed/packed data possible")
    return result

_SOURCE_PATTERNS = (
    ("dynamic_execution", re.compile(r"\b(exec|eval|loadstring)\s*\(", re.I)),
    ("dynamic_import", re.compile(r"__import__\s*\(|importlib\.import_module", re.I)),
    ("encoded_payload", re.compile(r"base64|b85decode|b64decode|marshal\.loads|zlib\.decompress", re.I)),
    ("process_memory_api", re.compile(r"/proc/[^\s'\" ]+/mem|process_vm_readv|ReadProcessMemory|ptrace\s*\(", re.I)),
    ("runtime_injection", re.compile(r"frida|gumjs|Interceptor\.attach|Module\.findExportByName", re.I)),
    ("anti_cheat_evasion_indicator", re.compile(r"anti.?cheat|noban|bypass|undetected|hide.?root|hide.?frida", re.I)),
    ("shell_execution", re.compile(r"os\.system|subprocess\.(Popen|run|call)|system\s*\(", re.I)),
)

def scan_source_file(path):
    """Static-only source triage; indicators are not proof of malicious behavior."""
    p = Path(path)
    if p.stat().st_size > 16777216:
        raise ValueError("source triage input exceeds 16 MiB safety limit")
    raw = p.read_bytes()
    text = raw.decode("utf-8", "replace")
    findings = []
    for label, pattern in _SOURCE_PATTERNS:
        hits = []
        for match in pattern.finditer(text):
            hits.append(text.count("\n", 0, match.start()) + 1)
            if len(hits) >= 20:
                break
        if hits:
            findings.append({"indicator": label, "lines": hits})
    return {"file": p.name, "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "findings": findings,
            "execution_performed": False,
            "note": "Static indicators only; manually review context before use."}

def inspect_dump_file(path, block_size=65536):
    """Read-only offline dump report; streams data and never acquires live memory."""
    p = Path(path)
    block_size = max(4096, min(int(block_size), 1048576))
    digest = hashlib.sha256()
    blocks = []
    strings = []
    carry = b""
    offset = 0
    with p.open("rb") as handle:
        while True:
            chunk = handle.read(block_size)
            if not chunk:
                break
            digest.update(chunk)
            if len(blocks) < 256:
                blocks.append((offset, round(_entropy(chunk), 3), len(chunk)))
            scan = carry + chunk
            base = offset - len(carry)
            for match in re.finditer(rb"[\\x20-\\x7e]{6,}", scan):
                strings.append((max(0, base + match.start()),
                                match.group(0).decode("ascii", "replace")[:160]))
                if len(strings) >= 100:
                    break
            carry = scan[-5:]
            offset += len(chunk)
    return {"file": p.name, "size": offset, "sha256": digest.hexdigest(),
            "block_size": block_size, "blocks": blocks, "strings": strings,
            "memory_acquisition": False, "secret_extraction": False}
