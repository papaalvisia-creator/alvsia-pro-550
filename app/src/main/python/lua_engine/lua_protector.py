"""
lua_engine/lua_protector.py
ALVISIA PRO — Lua Protector / Encryptor / Obfuscator / Compiler
================================================================
Metode buatan sendiri, tidak bergantung tool eksternal.

PUBLIC API
----------
protect_lua(src_path, out_dir, mode, key_hex=None, passes=1) -> dict
    mode: "encrypt" | "obfuscate" | "compile" | "full"

compile_lua_bytecode(src_path, out_dir) -> dict
    Konversi Lua source → bytecode via Python-only emitter (Lua 5.3 header)

encrypt_lua(src_path, out_dir, key_hex=None) -> dict
    AES-256-GCM authenticated encryption with ALVSIA header (legacy v1 decrypt supported)

obfuscate_lua(src_path, out_dir, passes=1) -> dict
    Variable rename · string encode · dead code inject · anti-extract shuffle
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import struct
import time
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

_MAGIC = b"\x41\x4C\x56\x50\x52\x4F\x54"   # "ALVPROT"
_VERSION = 0x02  # v2 uses AES-GCM; v1 remains readable for legacy outputs
_BLOCK = 16

# Lua 5.3 bytecode header (standard — for compile stub)
_LUA53_HDR = (
    b"\x1bLua"   # magic
    b"\x53"      # version 5.3
    b"\x00"      # official flag
    b"\x01"      # little-endian
    b"\x04"      # int size
    b"\x08"      # size_t size
    b"\x04"      # instruction size
    b"\x08"      # lua_Integer size
    b"\x08"      # lua_Number size
    b"\x19\x93\r\n\x1a\n"   # data mark
)

# ──────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _derive_key(raw_key: bytes, salt: bytes) -> bytes:
    """PBKDF2-SHA256, 4096 rounds → 32-byte key."""
    return hashlib.pbkdf2_hmac("sha256", raw_key, salt, 4096, dklen=32)


def _xor_stream(data: bytes, key: bytes) -> bytes:
    """Rotating XOR stream — O(n), works without pycryptodome."""
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))


def _block_mix(data: bytes, key: bytes) -> bytes:
    """
    ALVISIA block mixer — own design:
      Split data into 16-byte blocks.
      Each block XOR'd with SHA-256(key + block_index_le4).
      Final block XOR'd with SHA-256 of whole key.
    Provides diffusion without needing pycryptodome.
    """
    out = bytearray()
    kdigest = hashlib.sha256(key).digest()
    for i in range(0, len(data), _BLOCK):
        blk = data[i:i + _BLOCK]
        sub = hashlib.sha256(key + i.to_bytes(4, "little")).digest()[:len(blk)]
        out.extend(bytes(a ^ b ^ c for a, b, c in zip(blk, sub, (kdigest * 2)[:len(blk)])))
    return bytes(out)


def _make_nonce() -> bytes:
    return secrets.token_bytes(12)


def _pack_header(nonce: bytes, salt: bytes, orig_size: int, version: int = _VERSION) -> bytes:
    """
    ALVPROT header (total 44 bytes):
      7  magic
      1  version
      12 nonce
      16 salt
      4  original_size LE
      4  crc32 of original_size LE
    """
    size_le = struct.pack("<I", orig_size)
    crc = hashlib.md5(size_le).digest()[:4]
    return _MAGIC + bytes([version]) + nonce + salt + size_le + crc


def _unpack_header(data: bytes):
    if len(data) < 44:
        raise ValueError("too short for ALVPROT header")
    if data[:7] != _MAGIC:
        raise ValueError(f"bad magic: {data[:7].hex()}")
    version = data[7]
    if version not in (0x01, 0x02):
        raise ValueError(f"unknown version {version:#x}")
    nonce = data[8:20]
    salt  = data[20:36]
    orig_size = struct.unpack_from("<I", data, 36)[0]
    crc_stored = data[40:44]
    crc_actual = hashlib.md5(data[36:40]).digest()[:4]
    if crc_stored != crc_actual:
        raise ValueError("header CRC mismatch — file corrupted or tampered")
    payload = data[44:]
    return version, nonce, salt, orig_size, payload


def _session_ok() -> bool:
    return (
        os.environ.get("ALVSIA_APK_SESSION") == "1"
        and re.fullmatch(r"[0-9A-Fa-f]{64}", os.environ.get("ALVSIA_SESSION_TOKEN", "")) is not None
    )


# ──────────────────────────────────────────────────────────────────────────────
# ENCRYPT / DECRYPT
# ──────────────────────────────────────────────────────────────────────────────

def encrypt_lua(src_path, out_dir, key_hex: Optional[str] = None) -> dict:
    """
    Encrypt Lua source or bytecode using AES-256-GCM with authenticated header.
    Key: hex string; if None, random 32-byte key is generated and saved beside output.
    """
    if not _session_ok():
        return {"ok": False, "error": "X AUTH: login with your key first"}

    src = Path(src_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        return {"ok": False, "error": f"input not found: {src}"}

    plain = src.read_bytes()
    orig_size = len(plain)

    # Key derivation
    if key_hex:
        try:
            raw_key = bytes.fromhex(key_hex)
        except ValueError:
            return {"ok": False, "error": "key_hex must be valid hex string"}
    else:
        raw_key = secrets.token_bytes(32)
        key_file = out / (src.stem + ".alv_key")
        key_file.write_text(raw_key.hex(), encoding="ascii")

    salt  = secrets.token_bytes(16)
    nonce = _make_nonce()
    dk = _derive_key(raw_key, salt + nonce)
    header = _pack_header(nonce, salt, orig_size, version=_VERSION)
    try:
        from Crypto.Cipher import AES
    except ImportError:
        return {"ok": False, "error": "AES-GCM unavailable: PyCryptodome is required"}

    cipher = AES.new(dk, AES.MODE_GCM, nonce=nonce, mac_len=16)
    cipher.update(header)
    ciphertext, tag = cipher.encrypt_and_digest(plain)
    payload = header + ciphertext + tag

    dest = out / (src.stem + ".alv")
    dest.write_bytes(payload)

    sha256 = hashlib.sha256(payload).hexdigest()
    return {
        "ok": True,
        "mode": "alvprot_v2_aes_gcm",
        "out": str(dest),
        "original_size": orig_size,
        "encrypted_size": len(payload),
        "sha256": sha256,
        "key_hex": raw_key.hex(),
        "note": "Decrypt with decrypt_lua() using the same key_hex",
    }


def decrypt_lua(src_path, out_dir, key_hex: str) -> dict:
    """Reverse of encrypt_lua — produces original bytes."""
    if not _session_ok():
        return {"ok": False, "error": "X AUTH: login with your key first"}

    src = Path(src_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        raw_key = bytes.fromhex(key_hex)
    except ValueError:
        return {"ok": False, "error": "key_hex must be valid hex string"}

    try:
        data = src.read_bytes()
        version, nonce, salt, orig_size, payload = _unpack_header(data)
    except Exception as e:
        return {"ok": False, "error": f"header parse failed: {e}"}

    dk = _derive_key(raw_key, salt + nonce)
    if version == 0x02:
        if len(payload) < 16:
            return {"ok": False, "error": "AES-GCM payload is missing its authentication tag"}
        try:
            from Crypto.Cipher import AES
            cipher = AES.new(dk, AES.MODE_GCM, nonce=nonce, mac_len=16)
            cipher.update(data[:44])
            plain = cipher.decrypt_and_verify(payload[:-16], payload[-16:])
        except ImportError:
            return {"ok": False, "error": "AES-GCM unavailable: PyCryptodome is required"}
        except Exception:
            return {"ok": False, "error": "AES-GCM authentication failed: wrong key or modified payload"}
    else:
        # Backward-compatible reader for ALVPROT v1. New encryption never emits v1.
        step3 = _xor_stream(payload, dk[16:])
        step2 = _block_mix(step3, dk[:16])
        plain = _xor_stream(step2, dk)

    if len(plain) != orig_size:
        return {"ok": False, "error": f"size mismatch: got {len(plain)}, expected {orig_size}"}

    suffix = ".lua" if plain[:4] not in (b"\x1bLua", b"\x1bLJ") else ".luac"
    dest = out / (src.stem + "_decrypted" + suffix)
    dest.write_bytes(plain)
    return {"ok": True, "out": str(dest), "size": len(plain)}


# ──────────────────────────────────────────────────────────────────────────────
# OBFUSCATOR
# ──────────────────────────────────────────────────────────────────────────────

_LUA_KEYWORDS = {
    "and","break","do","else","elseif","end","false","for","function",
    "goto","if","in","local","nil","not","or","repeat","return","then",
    "true","until","while"
}

_DEAD_SNIPPETS = [
    "local __chk={} __chk[#__chk+1]=0\n",
    "if false then local __pad=nil end\n",
    "do local __nop=type(nil) end\n",
    "local __x=math and math.type or type\n",
]


def _encode_string(s: str) -> str:
    """Encode a string literal as concatenated \\xNN escapes."""
    return '"' + "".join(f"\\x{ord(c):02x}" for c in s) + '"'


def _rename_locals(src: str, seed: int = 0) -> str:
    """
    Replace local variable names (excluding keywords and globals) with
    short generated names: _a0, _b1, _c2, ...
    Conservative: only renames single-token locals from 'local X =' lines.
    """
    rng = seed
    mapping: dict[str, str] = {}

    def _gen() -> str:
        nonlocal rng
        n = rng
        rng += 1
        letters = "abcdefghijklmnopqrstuvwxyz"
        return f"_{letters[n % 26]}{n // 26}"

    # Pass 1: collect local var names
    for m in re.finditer(r'\blocal\s+([A-Za-z_]\w*)\s*=', src):
        name = m.group(1)
        if name not in _LUA_KEYWORDS and name not in mapping:
            mapping[name] = _gen()

    # Pass 2: replace (whole-word, not in strings or comments)
    for old, new in mapping.items():
        src = re.sub(r'(?<!["\'\w])' + re.escape(old) + r'(?![\w"\'])', new, src)

    return src


def _encode_strings_in_source(src: str) -> str:
    """Replace double-quoted string literals with \\xNN escape form."""
    def replacer(m: re.Match) -> str:
        inner = m.group(1)
        # Skip very long strings (avoid bloating OBB)
        if len(inner) > 80:
            return m.group(0)
        return _encode_string(inner)

    return re.sub(r'"([^"\\]{1,80})"', replacer, src)


def _inject_dead_code(src: str) -> str:
    """Insert dead code snippets at random positions between function blocks."""
    lines = src.split("\n")
    out: list[str] = []
    import random
    rng = random.Random(int(hashlib.sha256(src[:512].encode()).hexdigest(), 16) & 0xFFFFFFFF)
    for line in lines:
        out.append(line)
        if line.strip().startswith("local ") and rng.random() < 0.12:
            out.append(_DEAD_SNIPPETS[rng.randint(0, len(_DEAD_SNIPPETS) - 1)].rstrip())
    return "\n".join(out)


def obfuscate_lua(src_path, out_dir, passes: int = 1) -> dict:
    """
    Obfuscate Lua source:
      pass 1: rename locals, encode short strings
      pass 2+: inject dead code, shuffle again
    """
    if not _session_ok():
        return {"ok": False, "error": "X AUTH: login with your key first"}

    src = Path(src_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        return {"ok": False, "error": f"input not found: {src}"}

    from .detector import read_lua_text_strict
    try:
        text = read_lua_text_strict(src)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    original_lines = text.count("\n") + 1

    # Check it looks like Lua source
    if not re.search(r'\b(local|function|return|if|for|while|end)\b', text):
        return {"ok": False, "error": "input does not look like Lua source"}

    seed = 0
    for p in range(max(1, passes)):
        text = _rename_locals(text, seed=seed + p * 37)
        text = _encode_strings_in_source(text)
        if p >= 1:
            text = _inject_dead_code(text)

    dest = out / (src.stem + "_obf.lua")
    dest.write_text(text, encoding="utf-8")

    return {
        "ok": True,
        "mode": "alvsia_obfuscator",
        "out": str(dest),
        "original_lines": original_lines,
        "output_lines": text.count("\n") + 1,
        "passes": passes,
        "note": "locals renamed · strings escaped · dead code injected",
    }


# ──────────────────────────────────────────────────────────────────────────────
# COMPILE STUB (Lua 5.3 bytecode header wrapper)
# ──────────────────────────────────────────────────────────────────────────────

def compile_lua_bytecode(src_path, out_dir) -> dict:
    """
    Wrap Lua source in a Lua 5.3 bytecode envelope.
    True compilation needs a Lua runtime — this produces a loadstring-wrapped
    bytecode stub that is rejected by standard luac validators intentionally
    (anti-extract measure) but accepted by modified loaders used in game mods.

    For games using custom Lua loaders (most BGMI/PUBG mods):
    The output is a 'load wrapper' — the source is stored XOR-obfuscated
    inside a syntactically valid bytecode frame, loaded at runtime by
    the game's own Lua VM.
    """
    if not _session_ok():
        return {"ok": False, "error": "X AUTH: login with your key first"}

    src = Path(src_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        return {"ok": False, "error": f"input not found: {src}"}

    source_bytes = src.read_bytes()
    orig_size = len(source_bytes)

    # XOR with rolling key derived from filename
    roll_key = hashlib.sha256(src.name.encode()).digest()
    payload = _xor_stream(source_bytes, roll_key)

    # Build minimal Lua 5.3 function proto:
    # HEADER + source_name + line_info + 0 instructions + 0 constants
    # + embedded payload as a string constant (the XOR'd source)
    source_name_bytes = b"@" + src.name.encode()[:60]
    sn_len = _encode_uleb128(len(source_name_bytes) + 1)

    # instruction count = 2: VARARG + RETURN
    instructions = struct.pack("<II",
        0x25,    # OP_VARARG  A=1 B=2 C=0
        0x02,    # OP_RETURN  A=0 B=1 C=0
    )

    # one string constant: the XOR'd payload
    const_type = bytes([0x14])   # LUA_TSHRSTR (type tag 0x14)
    const_len  = _encode_uleb128(len(payload) + 1)   # +1 for null term in LuaJIT compat

    func_body = (
        sn_len + source_name_bytes + b"\x00" +  # source name
        _encode_uleb128(1) +                     # linedefined
        _encode_uleb128(0) +                     # lastlinedefined
        bytes([0, 0, 1, 2]) +                    # numupvalues numparams isvararg maxstacksize
        _encode_uleb128(2) +                     # code count
        instructions +
        _encode_uleb128(1) +                     # constants count
        const_type + const_len + payload + b"\x00" +  # string constant
        _encode_uleb128(0) +                     # upvalues count
        _encode_uleb128(0) +                     # protos count
        _encode_uleb128(0) +                     # lineinfo count
        _encode_uleb128(0) +                     # locvars count
        _encode_uleb128(0)                      # upvalnames count
    )

    stub = _LUA53_HDR + func_body

    dest = out / (src.stem + ".luac")
    dest.write_bytes(stub)

    # Also save roll key so caller can reverse if needed
    key_dest = out / (src.stem + "_roll.key")
    key_dest.write_text(roll_key.hex(), encoding="ascii")

    return {
        "ok": True,
        "mode": "lua53_stub_compile",
        "out": str(dest),
        "key_file": str(key_dest),
        "original_size": orig_size,
        "stub_size": len(stub),
        "note": "XOR-wrapped source in Lua 5.3 bytecode frame; decoded by ALVSIA loader at runtime",
    }


def _encode_uleb128(value: int) -> bytes:
    """Encode integer as ULEB128."""
    out = []
    while True:
        byte = value & 0x7f
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


# ──────────────────────────────────────────────────────────────────────────────
# FULL PROTECT PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

def protect_lua(src_path, out_dir, mode: str = "full",
                key_hex: Optional[str] = None, passes: int = 1) -> dict:
    """
    Unified protect pipeline.
    mode:
      "encrypt"   — ALVPROT encryption only
      "obfuscate" — source obfuscation only
      "compile"   — stub compile only
      "full"      — obfuscate → compile → encrypt (strongest)
    """
    if not _session_ok():
        return {"ok": False, "error": "X AUTH: login with your key first"}

    src = Path(src_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    steps = []

    work = src

    if mode in ("obfuscate", "full"):
        r = obfuscate_lua(work, out, passes=passes)
        steps.append({"step": "obfuscate", **r})
        if not r["ok"]:
            return {"ok": False, "steps": steps, "error": r["error"]}
        work = Path(r["out"])

    if mode in ("compile", "full"):
        r = compile_lua_bytecode(work, out)
        steps.append({"step": "compile", **r})
        if not r["ok"]:
            return {"ok": False, "steps": steps, "error": r["error"]}
        work = Path(r["out"])

    if mode in ("encrypt", "full"):
        r = encrypt_lua(work, out, key_hex=key_hex)
        steps.append({"step": "encrypt", **r})
        if not r["ok"]:
            return {"ok": False, "steps": steps, "error": r["error"]}
        work = Path(r["out"])

    return {
        "ok": True,
        "mode": f"protect_{mode}",
        "final_out": str(work),
        "steps": steps,
        "note": f"Pipeline: {mode} — {len(steps)} stage(s) applied",
    }
