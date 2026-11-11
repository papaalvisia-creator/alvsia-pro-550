# -*- coding: utf-8 -*-
"""Bounded, offline decoder for the referenced IL2CPP global-metadata v39 header.

The input is never modified. The output is written atomically only after every
section descriptor has passed bounds validation.
"""
from __future__ import annotations

import hashlib
import os
import struct
import tempfile
from pathlib import Path

MAGIC = 0xFAB11BAF
VERSION = 39
XOR_KEY = 0xA5C3F19D
HEADER_SIZE = 0x17C
DESCRIPTOR_SIZE = 12
MAX_INPUT_BYTES = 128 * 1024 * 1024
CANONICAL_DESCRIPTOR_ORDER = (
    22, 11, 0, 2, 5, 16, 7, 27, 6, 29, 15, 30, 23, 4, 12, 19,
    20, 26, 13, 18, 14, 17, 8, 3, 10, 21, 28, 25, 1, 9, 24,
)


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def decode_metadata_v39_bytes(source):
    """Decode and validate a v39 metadata blob; return (bytes, report)."""
    raw = bytes(source)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("metadata input exceeds 128 MiB limit")
    if len(raw) < HEADER_SIZE:
        raise ValueError("metadata file is smaller than the v39 header")
    if _u32(raw, 0) != MAGIC:
        raise ValueError("invalid IL2CPP metadata magic")
    version = _u32(raw, 4)
    if version != VERSION:
        raise ValueError("unsupported metadata version: %s (expected 39)" % version)

    decoded = bytearray(raw)
    for offset in range(8, HEADER_SIZE, 4):
        struct.pack_into("<I", decoded, offset, _u32(decoded, offset) ^ XOR_KEY)

    count = (HEADER_SIZE - 8) // DESCRIPTOR_SIZE
    if len(CANONICAL_DESCRIPTOR_ORDER) != count:
        raise ValueError("internal descriptor map length mismatch")
    protected = [
        bytes(decoded[8 + index * DESCRIPTOR_SIZE:8 + (index + 1) * DESCRIPTOR_SIZE])
        for index in range(count)
    ]
    for canonical_index, protected_index in enumerate(CANONICAL_DESCRIPTOR_ORDER):
        start = 8 + canonical_index * DESCRIPTOR_SIZE
        decoded[start:start + DESCRIPTOR_SIZE] = protected[protected_index]

    sections = []
    ranges = []
    for index in range(count):
        offset = 8 + index * DESCRIPTOR_SIZE
        section_offset, section_size, section_count = struct.unpack_from("<III", decoded, offset)
        end = section_offset + section_size
        if (section_offset < HEADER_SIZE or section_offset > len(decoded)
                or section_size > len(decoded) or end < section_offset
                or end > len(decoded) or section_count >= 0x40000000):
            raise ValueError("invalid section descriptor %d (offset=%d size=%d count=%d)" %
                             (index, section_offset, section_size, section_count))
        sections.append({
            "index": index,
            "offset": section_offset,
            "size": section_size,
            "count": section_count,
            "end": end,
        })
        if section_size:
            ranges.append((section_offset, end, index))

    overlaps = []
    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            overlaps.append({"left": previous[2], "right": current[2]})

    output = bytes(decoded)
    report = {
        "ok": True,
        "format": "IL2CPP global-metadata v39 (XOR/header-order transform)",
        "version": version,
        "size": len(output),
        "section_count": count,
        "sections": sections,
        "overlaps": overlaps,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "input_modified": False,
    }
    return output, report


def decode_metadata_v39_file(input_path, output_path):
    """Decode to a separate file with atomic replacement and a validated report."""
    source = Path(input_path)
    target = Path(output_path)
    if not source.is_file():
        raise ValueError("metadata input file does not exist")
    if source.resolve() == target.resolve():
        raise ValueError("refusing to overwrite the original metadata input")
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("metadata input exceeds 128 MiB limit")
    raw = source.read_bytes()
    decoded, report = decode_metadata_v39_bytes(raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".alvsia-metadata-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(decoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, str(target))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    report["input"] = source.name
    report["output"] = str(target)
    return report
