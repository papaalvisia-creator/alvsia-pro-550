# -*- coding: utf-8 -*-
"""Bounded offline T24 Lua 5.3 bytecode normalizer.

This adapts the T24 opcode/string/line-info transform from the user's
PREMIUM.py reference into a side-effect-free Chaquopy-compatible module.
It never executes input bytecode and never overwrites the original file.
"""
from __future__ import annotations

import hashlib
import os
import struct
import tempfile
from pathlib import Path

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_ITEMS = 1_000_000
MAX_DEPTH = 128

# T24 opcode -> standard Lua 5.3 opcode. Entries are derived from the
# reference T24 v4 opcode-name table; unmapped opcodes retain identity
# semantics exactly as the reference converter did.
T24_TO_STD = {
    0: 13, 1: 14, 2: 15, 5: 18, 7: 20, 10: 23, 12: 25, 14: 27,
    15: 28, 16: 29, 17: 0, 18: 1, 20: 3, 21: 4, 22: 5, 23: 6,
    24: 7, 8: 8, 9: 9, 27: 10, 28: 11, 29: 12, 30: 30, 31: 31,
    32: 32, 33: 33, 34: 34, 35: 35, 36: 36, 37: 37, 38: 38,
    39: 39, 40: 40, 41: 41, 42: 42, 43: 43, 44: 44, 45: 45,
}


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def need(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError("truncated T24 bytecode at offset 0x%X" % self.pos)

    def raw(self, size):
        self.need(size)
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def u8(self):
        self.need(1)
        value = self.data[self.pos]
        self.pos += 1
        return value

    def i32(self):
        self.need(4)
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def u32(self):
        self.need(4)
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def u64(self):
        self.need(8)
        value = struct.unpack_from("<Q", self.data, self.pos)[0]
        self.pos += 8
        return value


class _Writer:
    def __init__(self):
        self.data = bytearray()

    def raw(self, value):
        self.data.extend(value)

    def u8(self, value):
        self.data.append(value & 0xff)

    def i32(self, value):
        self.data.extend(struct.pack("<i", int(value)))

    def u32(self, value):
        self.data.extend(struct.pack("<I", int(value) & 0xffffffff))

    def u64(self, value):
        self.data.extend(struct.pack("<Q", int(value)))


def convert_t24_to_standard(data, key):
    """Convert one T24 Lua 5.3 chunk to standard Lua 5.3 bytecode.

    T24 long strings use an eight-byte size_t field. The returned standard
    header is normalized to size_t=8. Pass an empty key for structure-only
    conversion; string constants then remain encoded and the report marks
    that limitation.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("T24 input must be bytes")
    data = bytes(data)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("T24 input exceeds 64 MiB limit")
    if len(data) < 35 or data[:4] != b"\x1bLua" or data[4] != 0x53:
        raise ValueError("not a T24 Lua 5.3 bytecode header")
    key = bytes(key or b"")
    if len(key) > 4096:
        raise ValueError("T24 XOR key length exceeds limit")

    reader = _Reader(data)
    writer = _Writer()
    header = bytearray(reader.raw(34))
    # Standard Lua 5.3 output uses an eight-byte size_t for long strings.
    header[13] = 8
    writer.raw(header)
    stats = {"prototypes": 0, "instructions": 0, "constants": 0,
             "strings": 0, "strings_decoded": bool(key), "lineinfo_checkpoints": 0}

    def read_string():
        size = reader.u8()
        if size == 0:
            writer.u8(0)
            return
        if size == 0xff:
            length_plus_one = reader.u64()
            if length_plus_one < 1 or length_plus_one > MAX_INPUT_BYTES:
                raise ValueError("invalid T24 long-string length")
            length = length_plus_one - 1
            writer.u8(0xff)
            writer.u64(length_plus_one)
        else:
            length = size - 1
            writer.u8(size)
        raw = reader.raw(length)
        if key:
            raw = bytes(value ^ key[index % len(key)] for index, value in enumerate(raw))
        writer.raw(raw)
        stats["strings"] += 1

    def convert_proto(depth):
        if depth > MAX_DEPTH:
            raise ValueError("T24 prototype nesting exceeds limit")
        stats["prototypes"] += 1
        if stats["prototypes"] > MAX_ITEMS:
            raise ValueError("T24 prototype count exceeds limit")

        read_string()
        line_defined = reader.i32()
        last_line_defined = reader.i32()
        writer.i32(line_defined)
        writer.i32(last_line_defined)
        writer.u8(reader.u8())
        writer.u8(reader.u8())
        writer.u8(reader.u8())

        code_count = reader.i32()
        if code_count < 0 or code_count > MAX_ITEMS:
            raise ValueError("invalid T24 instruction count")
        writer.i32(code_count)
        stats["instructions"] += code_count
        if stats["instructions"] > MAX_ITEMS:
            raise ValueError("T24 total instruction count exceeds limit")
        for _ in range(code_count):
            instruction = reader.u32()
            opcode = instruction & 0x3f
            standard_opcode = T24_TO_STD.get(opcode, opcode)
            writer.u32((instruction & ~0x3f) | standard_opcode)

        constant_count = reader.i32()
        if constant_count < 0 or constant_count > MAX_ITEMS:
            raise ValueError("invalid T24 constant count")
        writer.i32(constant_count)
        stats["constants"] += constant_count
        for _ in range(constant_count):
            kind = reader.u8()
            writer.u8(kind)
            if kind == 0:
                continue
            if kind == 1:
                writer.u8(reader.u8())
            elif kind == 3:
                writer.raw(reader.raw(8))
            elif kind == 19:
                writer.raw(reader.raw(8))
            elif kind in (4, 20):
                read_string()
            else:
                raise ValueError("unsupported T24 constant type %d" % kind)

        upvalue_count = reader.i32()
        if upvalue_count < 0 or upvalue_count > MAX_ITEMS:
            raise ValueError("invalid T24 upvalue count")
        writer.i32(upvalue_count)
        for _ in range(upvalue_count):
            writer.u8(reader.u8())
            writer.u8(reader.u8())

        child_count = reader.i32()
        if child_count < 0 or child_count > MAX_ITEMS:
            raise ValueError("invalid T24 nested prototype count")
        writer.i32(child_count)
        for _ in range(child_count):
            convert_proto(depth + 1)

        line_count = reader.i32()
        if line_count < 0 or line_count > MAX_ITEMS:
            raise ValueError("invalid T24 line-info count")
        if line_count not in (0, code_count):
            raise ValueError("T24 line-info count does not match instruction count")
        delta_bytes = reader.raw(line_count)
        absolute_count = reader.i32()
        if absolute_count < 0 or absolute_count > line_count:
            raise ValueError("invalid T24 absolute-line count")
        checkpoints = {}
        previous_pc = -1
        for _ in range(absolute_count):
            pc = reader.i32()
            absolute_line = reader.i32()
            if pc <= previous_pc or pc < 0 or pc >= line_count:
                raise ValueError("invalid T24 absolute-line checkpoint index")
            if delta_bytes[pc] != 0x80:
                raise ValueError("T24 absolute-line checkpoint lacks sentinel delta")
            checkpoints[pc] = absolute_line
            previous_pc = pc
        writer.i32(line_count)
        current_line = line_defined
        for pc, delta_byte in enumerate(delta_bytes):
            delta = delta_byte - 256 if delta_byte >= 0x80 else delta_byte
            if delta == -128:
                if pc not in checkpoints:
                    raise ValueError("missing T24 absolute-line checkpoint at pc %d" % pc)
                current_line = checkpoints[pc]
            else:
                current_line += delta
            writer.i32(current_line)
        stats["lineinfo_checkpoints"] += absolute_count

        local_count = reader.i32()
        if local_count < 0 or local_count > MAX_ITEMS:
            raise ValueError("invalid T24 local-variable count")
        writer.i32(local_count)
        for _ in range(local_count):
            read_string()
            writer.i32(reader.i32())
            writer.i32(reader.i32())

        name_count = reader.i32()
        if name_count < 0 or name_count > MAX_ITEMS:
            raise ValueError("invalid T24 upvalue-name count")
        writer.i32(name_count)
        for _ in range(name_count):
            read_string()

    try:
        convert_proto(0)
    except (IndexError, struct.error) as exc:
        raise ValueError("malformed T24 bytecode: %s" % exc)
    if reader.pos != len(data):
        # Trailing bytes are not silently treated as valid bytecode.
        raise ValueError("unexpected trailing data after T24 chunk")
    output = bytes(writer.data)
    if output[:4] != b"\x1bLua" or output[4] != 0x53:
        raise ValueError("normalized Lua header validation failed")
    report = {
        "ok": True,
        "format": "T24 Lua 5.3",
        "output_format": "standard Lua 5.3 bytecode",
        "input_size": len(data),
        "output_size": len(output),
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "key_supplied": bool(key),
        "strings_decoded": bool(key),
        "input_modified": False,
    }
    report.update(stats)
    return output, report


def convert_t24_file(input_path, output_path, key):
    """Write a validated normalized chunk to a separate file atomically."""
    source = Path(input_path)
    target = Path(output_path)
    if not source.is_file():
        raise ValueError("T24 input file does not exist")
    if source.resolve() == target.resolve():
        raise ValueError("refusing to overwrite original T24 input")
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("T24 input exceeds 64 MiB limit")
    raw = source.read_bytes()
    normalized, report = convert_t24_to_standard(raw, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".alvsia-t24-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(normalized)
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
