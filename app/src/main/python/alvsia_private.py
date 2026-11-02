# -*- coding: utf-8 -*-
"""
ALVSIA PRIVATE TOOL
===================
Private-tier engine for ALVSIA PRO.
All logic in this module is sealed under the ALVSIA session auth and
ALVSIA_SEALED_RUNTIME flag — sub-tools here are inaccessible without
a valid proof ticket from the ALVSIA panel.

Capabilities (integrated from source research):
  - ZUC-128 stream cipher (LFSR + BiU implementation)
  - AES key scanner (S-box / Rcon / expanded schedule detection)
  - XOR key recovery (multi-key-size IC analysis)
  - Lua bytecode parser (Lua 5.1 / 5.3 string + number extraction)
  - Lua proto writer (BGMI / HePing / Standard Lua 5.3 output)
  - BGMI + HePing Lua opcode maps (separate XOR keys, separate opcode tables)
  - Compression best-fit finder (ZLIB + ZSTD with target-size constraint)
  - APK structure auditor (manifest, DEX count, lib arches, signing block)
  - String constant recovery (XOR multi-key + entropy + context scoring)
  - PAK manifest generator (CSV entry list from TencentPakFile)
  - Entropy analyzer (per-block entropy map for binary forensics)

Authorship: ALVSIA PRIVATE TOOL
Protected under ALVSIA session runtime. All tool output paths use
ALVSIA_PRIVATE_OUT prefix.
"""

from __future__ import annotations
import struct as _struct
import hashlib as _hashlib
import zlib as _zlib
import re as _re
import zipfile as _zipfile
import os as _os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from functools import lru_cache

__all__ = [
    'ZUCCipher',
    'AESKeyScanner',
    'XORKeyRecovery',
    'LuaBytecodeParser',
    'AlvsiaLuaWriter',
    'CompressionBestFit',
    'APKAuditor',
    'StringConstantRecovery',
    'LuaOpcodeConverter',
    'EntropyAnalyzer',
    'PAKManifestGenerator',
]

# ══════════════════════════════════════════════════════════════════════════════
# § 1  ZUC-128 Stream Cipher
# ══════════════════════════════════════════════════════════════════════════════

_M31 = 0x7FFFFFFF
_ZUC_D = [
    0x44D7, 0x26BC, 0x626B, 0x135E, 0x5789, 0x35E2,
    0x7135, 0x09AF, 0x4D78, 0x2F13, 0x6BC4, 0x1AF1,
    0x5E26, 0x3C4D, 0x789A, 0x47AC,
]
_ZUC_S0 = (
    0x3e, 0x72, 0x5b, 0x47, 0xca, 0xe0, 0x00, 0x33, 0x04, 0xd1, 0x54, 0x98, 0x09, 0xb9, 0x6d, 0xcb,
    0x7b, 0x1b, 0xf9, 0x32, 0xaf, 0x9d, 0x6a, 0xa5, 0xb8, 0x2d, 0xfc, 0x1d, 0x08, 0x53, 0x03, 0x90,
    0x4d, 0x4e, 0x84, 0x99, 0xe4, 0xce, 0xd9, 0x91, 0xdd, 0xb6, 0x85, 0x48, 0x8b, 0x29, 0x6e, 0xac,
    0xcd, 0xc1, 0xf8, 0x1e, 0x73, 0x43, 0x69, 0xc6, 0xb5, 0xbd, 0xfd, 0x39, 0x63, 0x20, 0xd4, 0x38,
    0x76, 0x7d, 0xb2, 0xa7, 0xcf, 0xed, 0x57, 0xc5, 0xf3, 0x2c, 0xbb, 0x14, 0x21, 0x06, 0x55, 0x9b,
    0xe3, 0xef, 0x5e, 0x31, 0x4f, 0x7f, 0x5a, 0xa4, 0x0d, 0x82, 0x51, 0x49, 0x5f, 0xba, 0x58, 0x1c,
    0x4a, 0x16, 0xd5, 0x17, 0xa8, 0x92, 0x24, 0x1f, 0x8c, 0xff, 0xd8, 0xae, 0x2e, 0x01, 0xd3, 0xad,
    0x3b, 0x4b, 0xda, 0x46, 0xeb, 0xc9, 0xde, 0x9a, 0x8f, 0x87, 0xd7, 0x3a, 0x80, 0x6f, 0x2f, 0xc8,
    0xb1, 0xb4, 0x37, 0xf7, 0x0a, 0x22, 0x13, 0x28, 0x7c, 0xcc, 0x3c, 0x89, 0xc7, 0xc3, 0x96, 0x56,
    0x07, 0xbf, 0x7e, 0xf0, 0x0b, 0x2b, 0x97, 0x52, 0x35, 0x41, 0x79, 0x61, 0xa6, 0x4c, 0x10, 0xfe,
    0xbc, 0x26, 0x95, 0x88, 0x8a, 0xb0, 0xa3, 0xfb, 0xc0, 0x18, 0x94, 0xf2, 0xe1, 0xe5, 0xe9, 0x5d,
    0xd0, 0xdc, 0x11, 0x66, 0x64, 0x5c, 0xec, 0x59, 0x42, 0x75, 0x12, 0xf5, 0x74, 0x9c, 0xaa, 0x23,
    0x0e, 0x86, 0xab, 0xbe, 0x2a, 0x02, 0xe7, 0x67, 0xe6, 0x44, 0xa2, 0x6c, 0xc2, 0x93, 0x9f, 0xf1,
    0xf6, 0xfa, 0x36, 0xd2, 0x50, 0x68, 0x9e, 0x62, 0x71, 0x15, 0x3d, 0xd6, 0x40, 0xc4, 0xe2, 0x0f,
    0x8e, 0x83, 0x77, 0x6b, 0x25, 0x05, 0x3f, 0x0c, 0x30, 0xea, 0x70, 0xb7, 0xa1, 0xe8, 0xa9, 0x65,
    0x8d, 0x27, 0x1a, 0xdb, 0x81, 0xb3, 0xa0, 0xf4, 0x45, 0x7a, 0x19, 0xdf, 0xee, 0x78, 0x34, 0x60
)
_ZUC_S1 = (
    0x55, 0xc2, 0x63, 0x71, 0x3b, 0xc8, 0x47, 0x86, 0x9f, 0x3c, 0xda, 0x5b, 0x29, 0xaa, 0xfd, 0x77,
    0x8c, 0xc5, 0x94, 0x0c, 0xa6, 0x1a, 0x13, 0x00, 0xe3, 0xa8, 0x16, 0x72, 0x40, 0xf9, 0xf8, 0x42,
    0x44, 0x26, 0x68, 0x96, 0x81, 0xd9, 0x45, 0x3e, 0x10, 0x76, 0xc6, 0xa7, 0x8b, 0x39, 0x43, 0xe1,
    0x3a, 0xb5, 0x56, 0x2a, 0xc0, 0x6d, 0xb3, 0x05, 0x22, 0x66, 0xbf, 0xdc, 0x0b, 0xfa, 0x62, 0x48,
    0xdd, 0x20, 0x11, 0x06, 0x36, 0xc9, 0xc1, 0xcf, 0xf6, 0x27, 0x52, 0xbb, 0x69, 0xf5, 0xd4, 0x87,
    0x7f, 0x84, 0x4c, 0xd2, 0x9c, 0x57, 0xa4, 0xbc, 0x4f, 0x9a, 0xdf, 0xfe, 0xd6, 0x8d, 0x7a, 0xeb,
    0x2b, 0x53, 0xd8, 0x5c, 0xa1, 0x14, 0x17, 0xfb, 0x23, 0xd5, 0x7d, 0x30, 0x67, 0x73, 0x08, 0x09,
    0xee, 0xb7, 0x70, 0x3f, 0x61, 0xb2, 0x19, 0x8e, 0x4e, 0xe5, 0x4b, 0x93, 0x8f, 0x5d, 0xdb, 0xa9,
    0xad, 0xf1, 0xae, 0x2e, 0xcb, 0x0d, 0xfc, 0xf4, 0x2d, 0x46, 0x6e, 0x1d, 0x97, 0xe8, 0xd1, 0xe9,
    0x4d, 0x37, 0xa5, 0x75, 0x5e, 0x83, 0x9e, 0xab, 0x82, 0x9d, 0xb9, 0x1c, 0xe0, 0xcd, 0x49, 0x89,
    0x01, 0xb6, 0xbd, 0x58, 0x24, 0xa2, 0x5f, 0x38, 0x78, 0x99, 0x15, 0x90, 0x50, 0xb8, 0x95, 0xe4,
    0xd0, 0x91, 0xc7, 0xce, 0xed, 0x0f, 0xb4, 0x6f, 0xa0, 0xcc, 0xf0, 0x02, 0x4a, 0x79, 0xc3, 0xde,
    0xa3, 0xef, 0xea, 0x51, 0xe6, 0x6b, 0x18, 0xec, 0x1b, 0x2c, 0x80, 0xf7, 0x74, 0xe7, 0xff, 0x21,
    0x5a, 0x6a, 0x54, 0x1e, 0x41, 0x31, 0x92, 0x35, 0xc4, 0x33, 0x07, 0x0a, 0xba, 0x7e, 0x0e, 0x34,
    0x88, 0xb1, 0x98, 0x7c, 0xf3, 0x3d, 0x60, 0x6c, 0x7b, 0xca, 0xd3, 0x1f, 0x32, 0x65, 0x04, 0x28,
    0x64, 0xbe, 0x85, 0x9b, 0x2f, 0x59, 0x8a, 0xd7, 0xb0, 0x25, 0xac, 0xaf, 0x12, 0x03, 0xe2, 0xf2
)

def _zuc_sbox(x: int) -> int:
    return ((_ZUC_S0[(x >> 24) & 0xFF] << 24) |
            (_ZUC_S1[(x >> 16) & 0xFF] << 16) |
            (_ZUC_S0[(x >> 8) & 0xFF] << 8) |
            _ZUC_S1[x & 0xFF])
def _rot32(x: int, n: int) -> int: return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
def _zuc_l1(x: int) -> int: return x ^ _rot32(x,2) ^ _rot32(x,10) ^ _rot32(x,18) ^ _rot32(x,24)
def _zuc_l2(x: int) -> int: return x ^ _rot32(x,8) ^ _rot32(x,14) ^ _rot32(x,22) ^ _rot32(x,30)

def _zuc_lfsr_with_input(s: list, u: int) -> None:
    f = (pow(2,15)*s[15] + pow(2,17)*s[13] + pow(2,21)*s[10] +
         pow(2,20)*s[4]  + (1 + pow(2,8))*s[0] + u) % (2**31 - 1)
    s.pop(0); s.append(f if f else 0x7FFFFFFF)

def _zuc_lfsr_without_input(s: list) -> None:
    f = (pow(2,15)*s[15] + pow(2,17)*s[13] + pow(2,21)*s[10] +
         pow(2,20)*s[4]  + (1 + pow(2,8))*s[0]) % (2**31 - 1)
    s.pop(0); s.append(f if f else 0x7FFFFFFF)


class ZUCCipher:
    """ZUC-128 stream cipher — symmetric encrypt/decrypt.

    Used in some BGMI/PUBG PAK entries as an alternative to SM4.

    Usage::

        zuc = ZUCCipher(key_16b, iv_16b)
        plaintext = zuc.encrypt(ciphertext)   # same call for decrypt
    """

    def __init__(self, key: bytes, iv: bytes):
        if len(key) != 16: raise ValueError("ZUC key must be exactly 16 bytes")
        if len(iv)  != 16: raise ValueError("ZUC IV must be exactly 16 bytes")
        self.s  = [0] * 16
        self.r1 = 0
        self.r2 = 0
        self._init(key, iv)
        # ZUC discards one F output after the 32 initialization rounds.
        self._bit_reorganization()
        self._f()
        _zuc_lfsr_without_input(self.s)

    def _init(self, key: bytes, iv: bytes) -> None:
        for i in range(16):
            self.s[i] = ((key[i] << 23) | (_ZUC_D[i] << 8) | iv[i]) & _M31
        self.r1 = self.r2 = 0
        for _ in range(32):
            self._bit_reorganization()
            w = self._f() & 0xFFFFFFFF
            u = (w >> 1) & _M31
            _zuc_lfsr_with_input(self.s, u)

    def _bit_reorganization(self) -> None:
        s = self.s
        self.x = [
            ((s[15] & 0x7FFF8000) << 1) | (s[14] & 0xFFFF),
            ((s[11] & 0xFFFF) << 16)    | (s[9]  >> 15),
            ((s[7]  & 0xFFFF) << 16)    | (s[5]  >> 15),
            ((s[2]  & 0xFFFF) << 16)    | (s[0]  >> 15),
        ]

    def _f(self) -> int:
        w   = ((self.x[0] ^ self.r1) + self.r2) & 0xFFFFFFFF
        w1  = (self.r1 + self.x[1]) & 0xFFFFFFFF
        w2  = (self.r2 ^ self.x[2]) & 0xFFFFFFFF
        u   = _zuc_l1(((w1 << 16) | (w2 >> 16)) & 0xFFFFFFFF)
        v   = _zuc_l2(((w2 << 16) | (w1 >> 16)) & 0xFFFFFFFF)
        self.r1 = _zuc_sbox(u)
        self.r2 = _zuc_sbox(v)
        return w

    def _generate(self, n_words: int) -> bytes:
        out = bytearray()
        for _ in range(n_words):
            self._bit_reorganization()
            z = (self._f() ^ self.x[3]) & 0xFFFFFFFF
            _zuc_lfsr_without_input(self.s)
            out += _struct.pack(">I", z)
        return bytes(out)

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt (or decrypt — ZUC is symmetric) *data*."""
        ks = self._generate((len(data) + 3) // 4)
        return bytes(data[i] ^ ks[i] for i in range(len(data)))

    decrypt = encrypt  # alias


# ══════════════════════════════════════════════════════════════════════════════
# § 2  AES Key Scanner
# ══════════════════════════════════════════════════════════════════════════════

_AES_SBOX = bytes([
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
])
_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _entropy(data: bytes) -> float:
    if not data: return 0.0
    import math
    freq = [0] * 256
    for b in data: freq[b] += 1
    n = len(data)
    return -sum((c/n)*math.log2(c/n) for c in freq if c)

def _looks_like_key(data: bytes) -> bool:
    if len(data) not in (16, 24, 32): return False
    return _entropy(data) > 6.5

def _check_expanded_aes128(data: bytes, off: int) -> bool:
    """Verify 176-byte block looks like AES-128 key schedule."""
    if off + 176 > len(data): return False
    w = [0] * 44
    for i in range(4):
        w[i] = _struct.unpack_from('>I', data, off + i*4)[0]
    for i in range(4, 44):
        temp = w[i-1]
        if i % 4 == 0:
            temp = ((_AES_SBOX[(temp >> 16) & 0xFF] << 24) |
                    (_AES_SBOX[(temp >>  8) & 0xFF] << 16) |
                    (_AES_SBOX[(temp      ) & 0xFF] <<  8) |
                    (_AES_SBOX[(temp >> 24) & 0xFF]      ))
            temp ^= (_RCON[(i // 4) - 1] << 24)
        w[i] = w[i-4] ^ temp
    expected = bytearray()
    for word in w: expected += _struct.pack('>I', word)
    return bytes(expected) == data[off:off+176]


class AESKeyScanner:
    """Scan a binary blob for embedded AES key material.

    Detects:
    - AES S-box table presence (flags an AES implementation nearby)
    - AES Rcon table presence
    - Expanded AES-128 key schedules (176-byte blocks)
    - High-entropy 16/24/32-byte candidates near ``key``/``aes`` markers

    Usage::

        results = AESKeyScanner.scan(data)
        for hit in results:
            print(hit['type'], hit.get('raw_key',''), hit['offset'])
    """

    @staticmethod
    def scan(data: bytes) -> List[Dict]:
        results: List[Dict] = []

        # S-box
        off = data.find(_AES_SBOX)
        if off != -1:
            results.append({'type': 'sbox_table', 'offset': hex(off),
                            'note': 'AES S-box — implementation present'})
        # Rcon
        rcon = bytes(_RCON)
        off = data.find(rcon)
        if off != -1:
            results.append({'type': 'rcon_table', 'offset': hex(off),
                            'note': 'AES Rcon table'})

        # Expanded key schedules
        for i in range(0, len(data) - 176, 16):
            if _check_expanded_aes128(data, i):
                raw = data[i:i+16]
                results.append({'type': 'expanded_key_schedule',
                                'offset': hex(i), 'raw_key': raw.hex(),
                                'note': 'AES-128 expanded key schedule'})

        # High-entropy blocks near keyword markers
        markers = [b'aes', b'AES', b'key', b'KEY', b'cipher', b'CIPHER', b'secret']
        for marker in markers:
            pos = 0
            while True:
                pos = data.find(marker, pos)
                if pos == -1: break
                for sz in (16, 24, 32):
                    for candidate_off in range(max(0, pos-64), min(len(data)-sz, pos+64)):
                        candidate = data[candidate_off:candidate_off+sz]
                        if _looks_like_key(candidate):
                            results.append({'type': 'high_entropy_candidate',
                                           'offset': hex(candidate_off),
                                           'size': sz,
                                           'raw_key': candidate.hex(),
                                           'near_marker': marker.decode()})
                pos += 1

        # Deduplicate by offset
        seen: set = set()
        deduped = []
        for r in results:
            key = (r['type'], r['offset'])
            if key not in seen:
                seen.add(key); deduped.append(r)
        return deduped

    @staticmethod
    def scan_file(path: str) -> List[Dict]:
        return AESKeyScanner.scan(Path(path).read_bytes())


# ══════════════════════════════════════════════════════════════════════════════
# § 3  XOR Key Recovery (IC / Kasiski inspired)
# ══════════════════════════════════════════════════════════════════════════════

class XORKeyRecovery:
    """Recover XOR keys from ciphertext using Index of Coincidence analysis.

    Supports single-byte, multi-byte (up to 64-byte) keys.
    Returns a list of ``(key_len, key_bytes, score)`` candidates sorted by
    descending confidence.

    Usage::

        results = XORKeyRecovery.recover(ciphertext, max_key_len=32)
        key_len, key_bytes, score = results[0]
        plaintext = bytes(ciphertext[i] ^ key_bytes[i % key_len]
                          for i in range(len(ciphertext)))
    """

    # Expected frequency distribution for printable ASCII (English)
    _EXPECTED_IC = 0.0667
    _ASCII_FREQ = {
        0x20: 0.130, 0x65: 0.111, 0x74: 0.085, 0x61: 0.082,
        0x6f: 0.079, 0x69: 0.075, 0x6e: 0.071, 0x73: 0.063,
        0x72: 0.061, 0x68: 0.060, 0x6c: 0.041, 0x64: 0.038,
    }

    @staticmethod
    def _ic(data: bytes) -> float:
        n = len(data)
        if n < 2: return 0.0
        freq = [0] * 256
        for b in data: freq[b] += 1
        return sum(f * (f-1) for f in freq) / (n * (n-1)) if n > 1 else 0.0

    @staticmethod
    def _best_single_byte_key(stream: bytes) -> Tuple[int, float]:
        best_key, best_score = 0, -1.0
        for k in range(256):
            dec = bytes(b ^ k for b in stream)
            score = sum(XORKeyRecovery._ASCII_FREQ.get(b, 0.0) for b in dec)
            if score > best_score:
                best_score = score; best_key = k
        return best_key, best_score

    @staticmethod
    def recover(data: bytes, max_key_len: int = 64,
                min_printable: float = 0.50) -> List[Tuple[int, bytes, float]]:
        if len(data) < 32:
            return []
        results = []
        for kl in range(1, min(max_key_len + 1, len(data) // 4)):
            # IC test for this key length
            ic_sum = 0.0
            for offset in range(kl):
                stream = bytes(data[i] for i in range(offset, len(data), kl))
                ic_sum += XORKeyRecovery._ic(stream)
            avg_ic = ic_sum / kl
            if avg_ic < 0.04:  # too random — skip
                continue

            key_bytes = bytearray()
            total_score = 0.0
            for offset in range(kl):
                stream = bytes(data[i] for i in range(offset, len(data), kl))
                k, sc = XORKeyRecovery._best_single_byte_key(stream)
                key_bytes.append(k); total_score += sc

            # Verify: apply key and check printable ratio
            dec = bytes(data[i] ^ key_bytes[i % kl] for i in range(len(data)))
            printable = sum(1 for b in dec if 0x20 <= b < 0x7f) / len(dec)
            if printable >= min_printable:
                results.append((kl, bytes(key_bytes), total_score / kl))

        return sorted(results, key=lambda x: -x[2])


# ══════════════════════════════════════════════════════════════════════════════
# § 4  Lua Bytecode Parser (5.1 / 5.3 / BGMI variant)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LuaStringConst:
    offset: int
    value: str

@dataclass
class LuaNumberConst:
    offset: int
    value: float

@dataclass
class LuaProtoInfo:
    source_name: str
    line_defined: int
    last_line: int
    strings: List[LuaStringConst] = field(default_factory=list)
    numbers: List[LuaNumberConst] = field(default_factory=list)
    num_params: int = 0
    max_stack: int = 0
    n_instructions: int = 0
    n_constants: int = 0
    n_protos: int = 0


class LuaBytecodeParser:
    """Parse Lua 5.1 / 5.3 bytecode and extract string + number constants.

    Handles standard headers AND BGMI-style modified headers.
    Does NOT require the file to have valid opcodes — pure structural parse.

    Usage::

        parser = LuaBytecodeParser(data)
        info   = parser.parse()
        for s in info.strings: print(s.value)
    """

    def __init__(self, data: bytes):
        self._d  = bytearray(data)
        self._p  = 0
        self.ver = 0
        self.int_sz = 4          # sizeof(int), used by line-number fields
        self.szt_sz = 8
        self.ins_sz = 4
        self.lua_int_sz = 8      # sizeof(lua_Integer), used by integer constants
        self.num_sz = 8
        self.int_is_float = False

    def _u8(self) -> int:
        v = self._d[self._p]; self._p += 1; return v

    def _u32(self) -> int:
        v = _struct.unpack_from('<I', self._d, self._p)[0]; self._p += 4; return v

    def _u64(self) -> int:
        v = _struct.unpack_from('<Q', self._d, self._p)[0]; self._p += 8; return v

    def _dbl(self) -> float:
        v = _struct.unpack_from('<d', self._d, self._p)[0]; self._p += 8; return v

    def _int(self) -> int:
        return self._u64() if self.int_sz == 8 else self._u32()

    def _lua_integer(self) -> int:
        if self.lua_int_sz == 8:
            value = _struct.unpack_from('<q', self._d, self._p)[0]
        elif self.lua_int_sz == 4:
            value = _struct.unpack_from('<i', self._d, self._p)[0]
        else:
            raise ValueError("Unsupported lua_Integer size")
        self._p += self.lua_int_sz
        return value

    def _size_t(self) -> int:
        return self._u64() if self.szt_sz == 8 else self._u32()

    def _lua_string(self) -> Optional[str]:
        # DumpString stores the byte length INCLUDING the trailing NUL.
        # For Lua 5.3+, a 0xFF size byte means the actual size follows as size_t.
        if self.ver in (0x53, 0x54):
            sz_byte = self._u8()
            if sz_byte == 0:
                return None
            size = self._size_t() if sz_byte == 0xFF else sz_byte
        else:
            size = self._size_t()
            if size == 0:
                return None
        raw = bytes(self._d[self._p:self._p + size])
        self._p += size
        return raw.decode('utf-8', errors='replace').rstrip('\x00')

    def _parse_header(self) -> bool:
        if len(self._d) < 4 or self._d[:4] != b'\x1bLua':
            return False
        self._p = 4
        self.ver = self._u8()          # version
        self._u8()                      # format
        if self.ver == 0x53:
            self._p += 6               # LUAC_DATA
            self.int_sz  = self._u8()  # sizeof(int): line-defined fields
            self.szt_sz  = self._u8()
            self.ins_sz  = self._u8()
            self.lua_int_sz = self._u8()
            lua_num_sz   = self._u8()
            self._p += self.lua_int_sz  # LUAC_INT
            self._p += lua_num_sz       # LUAC_NUM
        elif self.ver == 0x51:
            self._u8()  # endianness flag; supported chunks are decoded little-endian
            self.int_sz  = self._u8()
            self.szt_sz  = self._u8()
            self.ins_sz  = self._u8()
            self.num_sz  = self._u8()
            self.int_is_float = bool(self._u8())
        else:
            # Unknown version — try heuristic skip to body
            self._p = min(33, len(self._d) - 1)
        return True

    def _parse_proto(self) -> LuaProtoInfo:
        """Parse one Lua function prototype for standard Lua 5.1 or 5.3 chunks."""
        info = LuaProtoInfo(source_name='', line_defined=0, last_line=0)
        try:
            # Lua 5.1 stores nups before source; Lua 5.3 does not.
            if self.ver == 0x51:
                self._u8()  # nups
            src = self._lua_string() or ''
            info.source_name = src
            info.line_defined = self._int()
            info.last_line = self._int()

            info.num_params = self._u8()
            self._u8()  # is_vararg
            info.max_stack = self._u8()

            n_ins = self._u32()
            info.n_instructions = n_ins
            self._p += n_ins * self.ins_sz

            n_const = self._u32()
            info.n_constants = n_const
            for _ in range(n_const):
                ct = self._u8()
                if ct == 0:  # nil
                    continue
                if ct == 1:  # boolean
                    self._u8()
                elif ct == 3:  # number (Lua 5.1) / float (Lua 5.3)
                    off = self._p
                    if self.ver == 0x51 and self.int_is_float:
                        if self.num_sz == 4:
                            value = _struct.unpack_from('<i', self._d, self._p)[0]
                        elif self.num_sz == 8:
                            value = _struct.unpack_from('<q', self._d, self._p)[0]
                        else:
                            raise ValueError("Unsupported Lua 5.1 number size")
                        self._p += self.num_sz
                    else:
                        if self.num_sz == 4:
                            value = _struct.unpack_from('<f', self._d, self._p)[0]
                        elif self.num_sz == 8:
                            value = _struct.unpack_from('<d', self._d, self._p)[0]
                        else:
                            raise ValueError("Unsupported Lua number size")
                        self._p += self.num_sz
                    info.numbers.append(LuaNumberConst(off, value))
                elif ct == 19 and self.ver == 0x53:  # Lua 5.3 integer
                    off = self._p
                    value = self._lua_integer()
                    info.numbers.append(LuaNumberConst(off, value))
                elif ct == 2 and self.ver == 0x51:  # legacy integer number
                    off = self._p
                    value = _struct.unpack_from('<i', self._d, self._p)[0]
                    self._p += 4
                    info.numbers.append(LuaNumberConst(off, value))
                elif ct in ((4,) if self.ver == 0x51 else (4, 20)):
                    off = self._p
                    value = self._lua_string()
                    if value is not None:
                        info.strings.append(LuaStringConst(off, value))
                else:
                    raise ValueError(f"Unsupported Lua constant tag {ct} for version {self.ver:#x}")

            if self.ver == 0x51:
                n_sub = self._u32()
                info.n_protos = n_sub
                for _ in range(n_sub):
                    sub = self._parse_proto()
                    info.strings.extend(sub.strings)
                    info.numbers.extend(sub.numbers)

                n_line = self._u32()
                self._p += n_line * self.int_sz
                n_loc = self._u32()
                for _ in range(n_loc):
                    self._lua_string()
                    self._int()
                    self._int()
                n_names = self._u32()
                for _ in range(n_names):
                    self._lua_string()
            else:
                n_up = self._u32()
                self._p += n_up * 2
                n_proto = self._u32()
                info.n_protos = n_proto
                for _ in range(n_proto):
                    sub = self._parse_proto()
                    info.strings.extend(sub.strings)
                    info.numbers.extend(sub.numbers)

                # Lua 5.3 debug tables: lineinfo ints, local variables, upvalue names.
                n_line = self._u32()
                self._p += n_line * self.int_sz
                n_loc = self._u32()
                for _ in range(n_loc):
                    self._lua_string()
                    self._int()
                    self._int()
                n_names = self._u32()
                for _ in range(n_names):
                    self._lua_string()
        except (IndexError, _struct.error) as exc:
            raise ValueError("Truncated or malformed Lua prototype") from exc
        return info
    def parse(self) -> LuaProtoInfo:
        """Parse the file and return a ``LuaProtoInfo`` with all constants."""
        if not self._parse_header():
            raise ValueError("Not a Lua bytecode file (missing \\x1bLua magic)")
        return self._parse_proto()


# ══════════════════════════════════════════════════════════════════════════════
# § 5  Lua Opcode Converter — BGMI + HePing + Standard
# ══════════════════════════════════════════════════════════════════════════════

# BGMI/PUBG Mobile opcode XOR key (from libUE4.so sub_777C014)
ALVSIA_BGMI_XOR_KEY = bytes([
    0x11,0x21,0x36,0x47,0x46,0x57,0xA7,0x8D,
    0x9D,0x84,0x90,0xD8,0xAB,0x00,0x8C,0x35,
    0x26,0x1A,0xF7,0xE4,0x58,0x05,0xB8,0xB3,
    0x15,0x07,0xD0,0x2C,0x1E,0x8F,0xF6,0xC8,
])

# HePing JY (和平精英) opcode XOR key (different build, different cipher)
ALVSIA_HEPING_XOR_KEY = bytes([
    0xEF,0xC1,0x71,0x3E,0x3F,0x34,0x70,0x24,
    0x58,0x61,0x9A,0x38,0x4F,0xA4,0x6D,0x08,
    0x64,0x70,0xAC,0xF2,0xBC,0xE6,0x2E,0x41,
    0x4F,0x00,0x83,0xE7,0x8B,0x20,0x07,0x00,
])

# BGMI → Standard Lua 5.3 opcode map (48 entries, extended from ldz.py)
ALVSIA_BGMI_TO_STD: Dict[int, int] = {
    0:13, 1:1,  2:2,  3:3,  4:4,  5:18, 6:6,  7:7,
    8:8,  9:9,  10:10,11:11,12:25,13:13,14:14,15:15,
    16:16,17:0, 18:1, 19:19,20:3, 21:4, 22:5, 23:6,
    24:7, 25:8, 26:9, 27:10,28:11,29:12,30:30,31:31,
    32:32,33:33,34:34,35:35,36:36,37:37,38:38,39:39,
    40:40,41:41,42:42,43:43,44:44,45:45,46:46,47:47,
}
ALVSIA_STD_TO_BGMI: Dict[int, int] = {v: k for k, v in ALVSIA_BGMI_TO_STD.items()
                                       if v not in [ALVSIA_BGMI_TO_STD[kk]
                                                    for kk in range(k)]}

# HePing → Standard opcode map (from lua.py, different scramble)
ALVSIA_HEPING_TO_STD: Dict[int, int] = {
    0:30, 1:31, 2:32, 3:33, 4:34, 5:30, 6:31, 7:32,
    8:33, 9:34, 10:30,11:31,12:41,13:13,14:14,15:15,
    16:16,17:17,18:18,19:19,20:20,21:21,22:22,23:23,
    24:24,25:25,26:26,27:27,28:28,29:29,30:30,31:31,
    32:32,33:33,34:34,35:35,36:36,37:37,38:38,39:39,
    40:40,41:41,42:42,43:43,44:44,45:45,46:46,47:47,
}

_STD_FMT = [0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
            0,0,0,0,0,0,2,0,0,0,0,0,0,0,2,2,0,2,0,1,0,3,0]

_LUA53_MAGIC_HEADER = (
    b'\x1bLua\x53\x00\x19\x93\r\n\x1a\n'
    b'\x04\x08\x04\x08\x08'
    b'\x78\x56\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x28\x77\x40'
)
_HDR_LEN = 33
_ENC_START = 0x22  # bytes before this are NOT XOR-encrypted


class LuaOpcodeConverter:
    """Convert the supported BGMI/HePing Lua 5.3 chunk variant to standard Lua 5.3.

    The reference tools transform string payloads while walking each Proto;
    they do NOT XOR the complete Proto body. Opcode remapping is independent.
    This implementation ports that structure with strict bounds/count checks.
    """

    VARIANT_BGMI = 'bgmi'
    VARIANT_HEPING = 'heping'

    def __init__(self, variant: str = 'bgmi'):
        self.variant = str(variant).lower()
        if self.variant == self.VARIANT_HEPING:
            self._xor_key = ALVSIA_HEPING_XOR_KEY
            self._op_map = ALVSIA_HEPING_TO_STD
        elif self.variant == self.VARIANT_BGMI:
            self._xor_key = ALVSIA_BGMI_XOR_KEY
            self._op_map = ALVSIA_BGMI_TO_STD
        else:
            raise ValueError('unsupported Lua variant: ' + self.variant)

    class _Reader:
        def __init__(self, data: bytes, key: bytes):
            self.data = memoryview(data)
            self.pos = 0
            self.key = key

        def read(self, size: int) -> bytes:
            if not isinstance(size, int) or size < 0 or self.pos + size > len(self.data):
                raise ValueError('truncated Lua variant at offset %d: need %s, have %d' %
                                 (self.pos, size, len(self.data) - self.pos))
            out = bytes(self.data[self.pos:self.pos + size])
            self.pos += size
            return out

        def u8(self) -> int:
            return self.read(1)[0]

        def u32(self) -> int:
            return _struct.unpack('<I', self.read(4))[0]

        def i32(self) -> int:
            return _struct.unpack('<i', self.read(4))[0]

        def i64(self) -> int:
            return _struct.unpack('<q', self.read(8))[0]

        def f64(self) -> float:
            return _struct.unpack('<d', self.read(8))[0]

        def string(self, encrypted: bool) -> bytes | None:
            size = self.u8()
            if size == 0xFF:
                size = self.u32()
            if size == 0:
                return None
            if size > len(self.data) - self.pos + 1:
                raise ValueError('Lua string length exceeds remaining input at offset %d' % self.pos)
            raw = self.read(size - 1)
            if encrypted:
                raw = bytes(value ^ self.key[i % len(self.key)] for i, value in enumerate(raw))
            return raw

    class _Writer:
        def __init__(self):
            self.data = bytearray()

        def raw(self, value: bytes):
            self.data.extend(value)

        def u8(self, value: int):
            self.data.append(value & 0xFF)

        def u32(self, value: int):
            self.data.extend(_struct.pack('<I', value))

        def i32(self, value: int):
            self.data.extend(_struct.pack('<i', value))

        def i64(self, value: int):
            self.data.extend(_struct.pack('<q', value))

        def f64(self, value: float):
            self.data.extend(_struct.pack('<d', value))

        def string(self, value: bytes | None):
            if value is None:
                self.u8(0)
                return
            size = len(value) + 1
            if size < 0xFF:
                self.u8(size)
            else:
                self.u8(0xFF)
                self.u32(size)
            self.raw(value)

    def _convert_proto(self, reader, writer, depth: int = 0):
        if depth > 200:
            raise ValueError('Lua prototype nesting exceeds safety limit')
        writer.string(reader.string(encrypted=True))
        line_defined = reader.i32()
        writer.i32(line_defined)
        writer.i32(reader.i32())
        writer.u8(reader.u8())
        writer.u8(reader.u8())
        writer.u8(reader.u8())

        code_count = reader.u32()
        if code_count == 0 or code_count > (len(reader.data) - reader.pos) // 4:
            raise ValueError('invalid instruction count %d at offset %d: %d bytes remain' %
                             (code_count, reader.pos, len(reader.data) - reader.pos))
        writer.u32(code_count)
        for _ in range(code_count):
            raw = reader.u32()
            old_op = raw & 0x3F
            if old_op >= len(_STD_FMT):
                raise ValueError('opcode out of range: %d' % old_op)
            new_op = self._op_map.get(old_op, old_op)
            if not isinstance(new_op, int) or new_op < 0 or new_op >= len(_STD_FMT):
                raise ValueError('opcode mapping out of range: %r' % (new_op,))
            a = (raw >> 6) & 0xFF
            b = (raw >> 23) & 0x1FF
            c = (raw >> 14) & 0x1FF
            bx = (raw >> 14) & 0x3FFFF
            sbx = bx - 131071
            ax = (raw >> 6) & 0x3FFFFFF
            fmt = _STD_FMT[new_op]
            if fmt == 0:
                converted = (new_op & 0x3F) | (a << 6) | (c << 14) | (b << 23)
            elif fmt == 1:
                converted = (new_op & 0x3F) | (a << 6) | (bx << 14)
            elif fmt == 2:
                converted = (new_op & 0x3F) | (a << 6) | (((sbx + 131071) & 0x3FFFF) << 14)
            else:
                converted = (new_op & 0x3F) | (ax << 6)
            writer.u32(converted)

        constant_count = reader.u32()
        if constant_count > len(reader.data) - reader.pos:
            raise ValueError('invalid constant count %d at offset %d' % (constant_count, reader.pos))
        writer.u32(constant_count)
        for _ in range(constant_count):
            tag = reader.u8()
            writer.u8(tag)
            if tag == 0:
                continue
            if tag == 1:
                writer.u8(reader.u8())
            elif tag == 3:
                writer.f64(reader.f64())
            elif tag == 19:
                writer.i64(reader.i64())
            elif tag in (4, 20):
                writer.string(reader.string(encrypted=True))
            else:
                raise ValueError('unsupported Lua constant tag %d at offset %d' % (tag, reader.pos - 1))

        upvalue_count = reader.u32()
        if upvalue_count > (len(reader.data) - reader.pos) // 2:
            raise ValueError('invalid upvalue count %d at offset %d' % (upvalue_count, reader.pos))
        writer.u32(upvalue_count)
        for _ in range(upvalue_count):
            writer.u8(reader.u8())
            writer.u8(reader.u8())

        child_count = reader.u32()
        if child_count > 100000:
            raise ValueError('nested prototype count exceeds safety limit')
        writer.u32(child_count)
        for _ in range(child_count):
            self._convert_proto(reader, writer, depth + 1)

        line_count = reader.u32()
        if line_count > (len(reader.data) - reader.pos):
            raise ValueError('invalid compressed lineinfo count %d at offset %d' % (line_count, reader.pos))
        lines = []
        current_line = line_defined
        for _ in range(line_count):
            delta = reader.u8()
            current_line += delta if delta <= 127 else delta - 256
            lines.append(current_line)
        writer.u32(len(lines))
        for line in lines:
            writer.i32(line)

        # The game variant carries an additional abslineinfo table; standard 5.3 does not.
        abs_count = reader.u32()
        if abs_count > (len(reader.data) - reader.pos) // 8:
            raise ValueError('invalid absolute lineinfo count %d at offset %d' % (abs_count, reader.pos))
        reader.read(abs_count * 8)

        local_count = reader.u32()
        if local_count > (len(reader.data) - reader.pos) // 9:
            raise ValueError('invalid local variable count %d at offset %d' % (local_count, reader.pos))
        writer.u32(local_count)
        for _ in range(local_count):
            writer.string(reader.string(encrypted=True))
            writer.i32(reader.i32())
            writer.i32(reader.i32())

        name_count = reader.u32()
        if name_count > (len(reader.data) - reader.pos):
            raise ValueError('invalid upvalue name count %d at offset %d' % (name_count, reader.pos))
        writer.u32(name_count)
        for _ in range(name_count):
            writer.string(reader.string(encrypted=True))

    def convert_bytes(self, data: bytes) -> bytes:
        """Decode only the known structured game variant; reject partial parses."""
        if len(data) < 34 or data[:4] != b'\\x1bLua' or data[4] != 0x53:
            raise ValueError('input is not a Lua 5.3 variant chunk')
        if data[5] != 0 or data[6:12] != b'\\x19\\x93\\x0d\\x0a\\x1a\\x0a':
            raise ValueError('Lua 5.3 check header does not match supported variant')
        if data[12] != 4 or data[13] != 4 or data[14] != 4 or data[15] != 8 or data[16] != 8:
            raise ValueError('unsupported variant field sizes: ' + data[12:17].hex())
        if data[17:25] != b'\\x78\\x56\\x00\\x00\\x00\\x00\\x00\\x00':
            raise ValueError('Lua integer check value mismatch')
        if _struct.unpack('<d', data[25:33])[0] != 370.5:
            raise ValueError('Lua number check value mismatch')
        reader = self._Reader(data, self._xor_key)
        reader.pos = 33
        writer = self._Writer()
        header = bytearray(data[:33])
        header[13] = 4
        writer.raw(header)
        writer.u8(reader.u8())  # main closure upvalue count
        self._convert_proto(reader, writer)
        if reader.pos != len(reader.data):
            raise ValueError('unexpected trailing bytes after Lua chunk: %d' % (len(reader.data) - reader.pos))
        converted = bytes(writer.data)
        # Verify the generated standard chunk with the strict in-app Lua 5.3 reader.
        from lua_engine.decompiler53 import load_chunk
        load_chunk(converted)
        return converted

    def convert_file(self, src: str, dst: str | None = None) -> bytes:
        result = self.convert_bytes(Path(src).read_bytes())
        if dst:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_bytes(result)
        return result

    def convert_folder(self, src_dir: str, dst_dir: str, glob: str = '*.luac') -> Dict[str, str]:
        out = Path(dst_dir)
        out.mkdir(parents=True, exist_ok=True)
        report: Dict[str, str] = {}
        for p in sorted(Path(src_dir).glob(glob)):
            try:
                self.convert_file(str(p), str(out / p.name))
                report[p.name] = 'OK'
            except Exception as exc:
                report[p.name] = 'FAIL: ' + str(exc)
        return report

# ══════════════════════════════════════════════════════════════════════════════
# § 6  Compression Best-Fit Finder
# ══════════════════════════════════════════════════════════════════════════════

try:
    from zstandard import ZstdCompressor as _ZstdC, ZstdDecompressor as _ZstdD
    _HAS_ZSTD = True
except ImportError:
    _HAS_ZSTD = False


class CompressionBestFit:
    """Find the compression level that fits data into a target byte budget.

    Tries ZLIB levels 9→1 and ZSTD levels 22→1 plus ultra negatives.
    Returns the smallest compressed result that still fits *target_size*,
    or the overall best if no target is given.

    Usage::

        result = CompressionBestFit.compress(data, method='zlib', target_size=4096)
        # result is bytes or None
    """

    @staticmethod
    def compress(data: bytes, method: str = 'zlib',
                 target_size: int = 0) -> Optional[bytes]:
        if method == 'zlib':
            for lvl in range(9, 0, -1):
                try:
                    c = _zlib.compress(data, lvl)
                    if target_size <= 0 or len(c) <= target_size:
                        return c
                except _zlib.error:
                    continue
            return None

        if method == 'zstd' and _HAS_ZSTD:
            levels = list(range(22, 0, -1)) + list(range(-1, -8, -1))
            for lvl in levels:
                try:
                    ctx  = _ZstdC(level=lvl)
                    c    = ctx.compress(data)
                    if target_size <= 0 or len(c) <= target_size:
                        return c
                except Exception:
                    continue
            return None

        raise ValueError(f"Unknown method: {method!r} (use 'zlib' or 'zstd')")

    @staticmethod
    def best_level_for_target(data: bytes, target_size: int,
                               method: str = 'zlib') -> Tuple[int, int]:
        """Return (level, compressed_size) for the largest result within budget.

        A result of (-1, 0) means no compression level fit the requested budget.
        """
        if target_size < 0:
            raise ValueError("target_size must be >= 0")
        if method == 'zlib':
            levels = range(9, 0, -1)
            compress = lambda level: _zlib.compress(data, level)
        elif method == 'zstd':
            if not _HAS_ZSTD:
                raise ValueError("zstandard dependency is not available")
            levels = list(range(22, 0, -1)) + list(range(-1, -8, -1))
            compress = lambda level: _ZstdC(level=level).compress(data)
        else:
            raise ValueError(f"Unknown method: {method!r} (use 'zlib' or 'zstd')")

        best_lvl, best_sz = -1, 0
        for lvl in levels:
            try:
                compressed = compress(lvl)
                fits = target_size <= 0 or len(compressed) <= target_size
                improves = (
                    best_lvl == -1
                    or (len(compressed) < best_sz if target_size == 0
                        else len(compressed) > best_sz)
                )
                if fits and improves:
                    best_lvl, best_sz = lvl, len(compressed)
            except Exception:
                continue
        return best_lvl, best_sz

# ══════════════════════════════════════════════════════════════════════════════
# § 7  APK Auditor
# ══════════════════════════════════════════════════════════════════════════════

class APKAuditor:
    """Structural APK audit — no decompilation needed.

    Extracts:
    - AndroidManifest.xml raw bytes + package name / version
    - DEX file count
    - Native library architectures present
    - Signing block presence (V2/V3 signature)
    - File count and size stats
    - Suspicious entries (oversized DEX, unusual extensions)

    Usage::

        report = APKAuditor.audit('/path/to/app.apk')
        print(report['package'])
    """

    @staticmethod
    def _find_package(manifest_raw: bytes) -> str:
        """Best-effort package name extraction from binary AndroidManifest."""
        # Package name appears as a UTF-16-LE string after the 'package' attribute
        m = _re.search(rb'p\x00a\x00c\x00k\x00a\x00g\x00e\x00'
                       rb'(?:.*?)'
                       rb'((?:[a-z0-9._]\x00){5,})', manifest_raw, _re.DOTALL)
        if m:
            raw = m.group(1)
            return raw[::2].decode('ascii', errors='replace').rstrip('\x00')
        # Fallback: look for com.* pattern
        m2 = _re.search(rb'com\.[a-z0-9.]{4,}', manifest_raw)
        if m2:
            return m2.group(0).decode('ascii', errors='replace')
        return 'unknown'

    @staticmethod
    def _has_v2_sig(apk_bytes: bytes) -> bool:
        return b'APK Sig Block 42' in apk_bytes

    @staticmethod
    def audit(path: str) -> Dict[str, Any]:
        path = str(path)
        result: Dict[str, Any] = {
            'path': path, 'package': 'unknown', 'version': 'unknown',
            'dex_count': 0, 'native_arches': [], 'signing_block_v2': False,
            'total_files': 0, 'total_size_kb': 0,
            'suspicious': [], 'lib_files': [], 'manifest_present': False,
        }
        try:
            raw = Path(path).read_bytes()
            result['signing_block_v2'] = APKAuditor._has_v2_sig(raw)
            result['total_size_kb'] = len(raw) // 1024

            with _zipfile.ZipFile(path, 'r') as zf:
                names = zf.namelist()
                result['total_files'] = len(names)
                arches: set = set()
                for name in names:
                    if name == 'AndroidManifest.xml':
                        result['manifest_present'] = True
                        try:
                            mraw = zf.read(name)
                            result['package'] = APKAuditor._find_package(mraw)
                        except Exception:
                            pass
                    if name.endswith('.dex'):
                        result['dex_count'] += 1
                        info = zf.getinfo(name)
                        if info.file_size > 20 * 1024 * 1024:
                            result['suspicious'].append(
                                f'Oversized DEX: {name} ({info.file_size//1024}KB)')
                    if name.startswith('lib/'):
                        parts = name.split('/')
                        if len(parts) >= 3:
                            arches.add(parts[1])
                        result['lib_files'].append(name)
                    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
                    if ext in ('exe', 'sh', 'bat', 'js', 'vbs', 'ps1'):
                        result['suspicious'].append(f'Unusual file: {name}')
                result['native_arches'] = sorted(arches)
        except (_zipfile.BadZipFile, Exception) as e:
            result['error'] = str(e)
        return result

    @staticmethod
    def audit_file(path: str) -> str:
        """Return a human-readable audit summary string."""
        r = APKAuditor.audit(path)
        lines = [
            f"ALVSIA APK AUDIT — {r['path']}",
            f"  Package   : {r['package']}",
            f"  Size      : {r['total_size_kb']} KB",
            f"  Files     : {r['total_files']}",
            f"  DEX count : {r['dex_count']}",
            f"  Native    : {', '.join(r['native_arches']) or 'none'}",
            f"  Sig V2/V3 : {r['signing_block_v2']}",
        ]
        if r['suspicious']:
            lines.append("  Suspicious:")
            for s in r['suspicious']: lines.append(f"    ! {s}")
        if 'error' in r:
            lines.append(f"  ERROR: {r['error']}")
        return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# § 8  String Constant Recovery
# ══════════════════════════════════════════════════════════════════════════════

class StringConstantRecovery:
    """Recover obfuscated string constants from binary blobs.

    Attempts multiple strategies in order:
    1. XOR single-byte key scan (IC-guided)
    2. XOR multi-byte key (up to 32 bytes, IC analysis)
    3. Base64 decode then UTF-8
    4. Reverse / ROT-n
    5. Raw printable ASCII extraction (fallback)

    Returns a list of ``{'method', 'key', 'strings'}`` dicts.

    Usage::

        results = StringConstantRecovery.recover(data)
        for r in results: print(r['method'], r['strings'][:5])
    """

    @staticmethod
    def _printable_strings(data: bytes, min_len: int = 6) -> List[str]:
        result, buf = [], []
        for b in data:
            if 0x20 <= b < 0x7f:
                buf.append(chr(b))
            else:
                if len(buf) >= min_len:
                    result.append(''.join(buf))
                buf = []
        if len(buf) >= min_len:
            result.append(''.join(buf))
        return result

    @staticmethod
    def recover(data: bytes, min_len: int = 6) -> List[Dict]:
        results = []

        # Strategy 1 & 2: XOR key recovery
        xor_candidates = XORKeyRecovery.recover(data, max_key_len=32)
        for kl, key, score in xor_candidates[:5]:
            dec = bytes(data[i] ^ key[i % kl] for i in range(len(data)))
            strs = StringConstantRecovery._printable_strings(dec, min_len)
            if strs:
                results.append({
                    'method': f'xor-{kl}byte',
                    'key': key.hex(),
                    'score': round(score, 3),
                    'strings': strs[:50],
                })

        # Strategy 3: base64 segments
        import base64
        for m in _re.finditer(rb'[A-Za-z0-9+/]{20,}={0,2}', data):
            try:
                dec = base64.b64decode(m.group(0))
                strs = StringConstantRecovery._printable_strings(dec, min_len)
                if strs:
                    results.append({'method': 'base64', 'key': '',
                                    'score': 0.5, 'strings': strs[:20]})
            except Exception:
                pass

        # Strategy 4: reversed chunk
        rev = data[::-1]
        strs = StringConstantRecovery._printable_strings(rev, min_len)
        if strs:
            results.append({'method': 'reversed', 'key': '', 'score': 0.3,
                            'strings': strs[:20]})

        # Fallback: raw printable
        raw_strs = StringConstantRecovery._printable_strings(data, min_len)
        if raw_strs:
            results.append({'method': 'raw_printable', 'key': '', 'score': 0.1,
                            'strings': raw_strs[:50]})

        return sorted(results, key=lambda x: -x['score'])


# ══════════════════════════════════════════════════════════════════════════════
# § 9  Entropy Analyzer
# ══════════════════════════════════════════════════════════════════════════════

class EntropyAnalyzer:
    """Compute per-block entropy map for binary forensics.

    Useful for finding: encrypted regions (H≈8.0), compressed regions (H>7.0),
    code segments (H≈5.5-6.5), and null/padding regions (H<1.0).

    Usage::

        blocks = EntropyAnalyzer.analyze(data, block_size=1024)
        for off, h in blocks:
            if h > 7.5: print(f'0x{off:08x}  H={h:.2f}  (encrypted/compressed)')
    """

    @staticmethod
    def block_entropy(data: bytes) -> float:
        if not data: return 0.0
        import math
        freq = [0] * 256
        for b in data: freq[b] += 1
        n = len(data)
        return -sum((c/n)*math.log2(c/n) for c in freq if c)

    @staticmethod
    def analyze(data: bytes, block_size: int = 1024) -> List[Tuple[int, float]]:
        """Return list of (offset, entropy) for each block."""
        return [(i, EntropyAnalyzer.block_entropy(data[i:i+block_size]))
                for i in range(0, len(data), block_size)]

    @staticmethod
    def summary(data: bytes, block_size: int = 1024) -> Dict[str, Any]:
        """Return summary: high-entropy, low-entropy, and suspicious regions."""
        blocks = EntropyAnalyzer.analyze(data, block_size)
        high   = [(off, h) for off, h in blocks if h >= 7.5]
        low    = [(off, h) for off, h in blocks if h <= 1.0]
        mid    = [(off, h) for off, h in blocks if 5.0 <= h < 7.5]
        return {
            'total_blocks'  : len(blocks),
            'high_entropy'  : high,    # likely encrypted/compressed
            'low_entropy'   : low,     # padding / null regions
            'code_like'     : mid,     # likely code/data
            'overall_mean'  : round(sum(h for _, h in blocks) / len(blocks), 3)
                              if blocks else 0.0,
        }

    @staticmethod
    def analyze_file(path: str, block_size: int = 4096) -> Dict[str, Any]:
        return EntropyAnalyzer.summary(Path(path).read_bytes(), block_size)


# ══════════════════════════════════════════════════════════════════════════════
# § 10  Alvsia Lua Writer (BGMI → Standard proto writer)
# ══════════════════════════════════════════════════════════════════════════════

class AlvsiaLuaWriter:
    """Low-level Lua 5.3 proto writer.

    Accepts a parsed proto tree and serializes it to standard Lua 5.3 bytecode.
    Used internally by LuaOpcodeConverter and available standalone for proto
    reconstruction workflows.

    Usage::

        w = AlvsiaLuaWriter(mode='std53')
        w.write_header()
        w.write_proto(proto_dict)
        output = w.get_bytes()
    """

    def __init__(self, mode: str = 'std53'):
        self._buf   = bytearray()
        self._mode  = mode
        self.int_sz = 8
        self.szt_sz = 8

    def _w(self, b: bytes)    -> None: self._buf.extend(b)
    def _u8(self, v: int)     -> None: self._buf.append(v & 0xFF)
    def _i32(self, v: int)    -> None: self._w(_struct.pack('<i', v))
    def _i64(self, v: int)    -> None: self._w(_struct.pack('<q', v))
    def _dbl(self, v: float)  -> None: self._w(_struct.pack('<d', v))
    def _u32(self, v: int)    -> None: self._w(_struct.pack('<I', v))
    def _int(self, v: int)    -> None: self._i64(v) if self.int_sz==8 else self._i32(v)
    def _size_t(self, v: int) -> None: self._i64(v) if self.szt_sz==8 else self._i32(v)

    def _lua_string(self, s: Optional[str]) -> None:
        if s is None: self._u8(0); return
        raw = s.encode('utf-8') + b'\x00'
        n   = len(raw)
        if n < 0xFF: self._u8(n + 1)
        else:        self._u8(0xFF); self._size_t(n + 1)
        self._w(raw[:-1])  # Lua stores without null terminator in 5.3

    def write_header(self) -> None:
        self._w(_LUA53_MAGIC_HEADER)

    def write_proto(self, p: Dict[str, Any]) -> None:
        """Write one proto dict (keys: source, line_def, last_line, params,
        is_vararg, max_stack, code, constants, upvalues, protos)."""
        self._lua_string(p.get('source'))
        self._int(p.get('line_def', 0))
        self._int(p.get('last_line', 0))
        self._u8(p.get('params', 0))
        self._u8(1 if p.get('is_vararg') else 0)
        self._u8(p.get('max_stack', 2))
        code = p.get('code', [])
        self._u32(len(code))
        for ins in code: self._u32(ins)
        consts = p.get('constants', [])
        self._u32(len(consts))
        for c in consts:
            t = c.get('type', 0)
            self._u8(t)
            if   t == 1:  self._u8(1 if c.get('value') else 0)
            elif t == 3:  self._dbl(float(c.get('value', 0)))
            elif t == 2:  self._int(int(c.get('value', 0)))
            elif t in (4,20): self._lua_string(str(c.get('value', '')))
        ups = p.get('upvalues', [])
        self._u32(len(ups))
        for u in ups: self._u8(u.get('instack',0)); self._u8(u.get('idx',0))
        protos = p.get('protos', [])
        self._u32(len(protos))
        for sub in protos: self.write_proto(sub)
        # line info / local vars / upvalue names (empty)
        self._u32(0); self._u32(0); self._u32(0)

    def get_bytes(self) -> bytes:
        return bytes(self._buf)


# ══════════════════════════════════════════════════════════════════════════════
# § 11  PAK Manifest Generator
# ══════════════════════════════════════════════════════════════════════════════

class PAKManifestGenerator:
    """Generate a CSV manifest of all entries in a TencentPakFile.

    Output columns:
    ``path, original_size, compressed_size, encryption, compression, n_blocks, sha256``

    Usage::

        gen  = PAKManifestGenerator('/path/to/game.pak')
        csv  = gen.generate()
        Path('/out/manifest.csv').write_text(csv)
    """

    def __init__(self, pak_path: str):
        self.pak_path = pak_path

    def generate(self) -> str:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from alvsia_core import TencentPakFile
        lines = ['path,original_size,compressed_size,encryption,compression,n_blocks,sha256_compressed']
        try:
            pak = TencentPakFile(self.pak_path)
            for entry_path, entry in pak.entries.items():
                # Compute SHA-256 of the raw compressed bytes (first block, approx)
                try:
                    first_block = pak._file_content[
                        entry.compressed_blocks[0].start:entry.compressed_blocks[0].end
                    ] if entry.compressed_blocks else b''
                    sha = _hashlib.sha256(bytes(first_block[:65536])).hexdigest()[:16]
                except Exception:
                    sha = 'n/a'
                orig = getattr(entry, 'uncompressed_size', 0) or 0
                comp = sum(b.end - b.start for b in entry.compressed_blocks)
                lines.append(
                    f'"{entry_path}",{orig},{comp},'
                    f'{entry.encryption_method},{entry.compression_method},'
                    f'{len(entry.compressed_blocks)},{sha}'
                )
        except Exception as e:
            lines.append(f'"ERROR",0,0,0,0,0,{str(e)[:60]}')
        return '\n'.join(lines)
