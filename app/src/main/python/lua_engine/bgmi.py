from __future__ import annotations
import struct

# Independent implementation of the BGMI / HePing Lua 5.3 structure transform.
#
# Two directions are supported:
#   decrypt=True   BGMI bytecode  -> standard Lua 5.3 bytecode
#   decrypt=False  standard Lua 5.3 bytecode -> BGMI bytecode
#
# Differences handled here:
#   * opcode permutation (BGMI_STD / STD_BGMI)
#   * size_t width (BGMI uses 4 bytes, standard desktop luac uses 8)
#   * line info encoding (BGMI stores signed byte deltas plus an absolute
#     count, standard Lua 5.3 stores one int32 per instruction)
#   * string constants XOR-encoded with a caller-supplied repeating key.
#
# Passing an empty/None key switches to structure-only mode: the structure is
# normalised but encoded string payloads are copied byte-for-byte.  This is
# intentional - the caller may not have the key yet and must never receive a
# half-decoded chunk that looks valid.
BGMI_STD = {0:13,1:14,2:15,3:16,4:17,5:18,14:27,16:29,17:0,18:1,
            20:3,21:4,22:5,23:6,24:7,25:8,26:9,27:10,28:11,29:12,
            30:30,31:31,32:32,33:33,34:34,36:36,37:37,38:38,39:39,
            40:40,41:41,42:42,43:43,44:44,45:45}
STD_BGMI={v:k for k,v in BGMI_STD.items()}
# Instruction format per *standard* Lua 5.3 opcode:
# 0 = iABC, 1 = iABx, 2 = iAsBx, 3 = iAx
STD_FMT=[0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,0,0,0,0,0,0,0,2,2,0,2,0,1,0,3]
MAXARG_Bx = (1 << 18) - 1
MAXARG_sBx = MAXARG_Bx >> 1


def _size_fmt(width: int) -> str:
    if width == 4:
        return "<I"
    if width == 8:
        return "<Q"
    raise ValueError(f"unsupported size_t width {width}")


class _R:
    def __init__(self, d):
        self.d = d
        self.p = 0

    def need(self, n):
        if n < 0 or self.p + n > len(self.d):
            raise ValueError("truncated Lua chunk")

    def byte(self):
        self.need(1)
        v = self.d[self.p]
        self.p += 1
        return v

    def u32(self):
        self.need(4)
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        self.need(4)
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def sizet(self, width):
        self.need(width)
        v = struct.unpack_from(_size_fmt(width), self.d, self.p)[0]
        self.p += width
        return v

    def raw(self, n):
        self.need(n)
        v = self.d[self.p:self.p + n]
        self.p += n
        return v


class _W:
    def __init__(self):
        self.b = bytearray()

    def byte(self, v):
        self.b.append(v & 255)

    def u32(self, v):
        self.b.extend(struct.pack("<I", v & 0xffffffff))

    def i32(self, v):
        self.b.extend(struct.pack("<i", int(v)))

    def sizet(self, v, width):
        self.b.extend(struct.pack(_size_fmt(width), int(v)))

    def raw(self, d):
        self.b.extend(d)


def _scan_opcodes_from(data: bytes, start: int, decrypt: bool) -> None:
    """Parse the top-level proto body from *start* and scan its instruction array.

    Raises ValueError("unsupported BGMI opcode N") on the first unknown opcode.
    """
    # Input ABI: BGMI chunks use 4-byte size_t, standard chunks use 8.
    in_width = 4 if decrypt else 8
    r = _R(data)
    r.p = start
    r.byte()          # upvalue count
    sz = r.byte()     # source string length prefix
    if sz == 255:
        sz = r.sizet(in_width)
    if sz > 0:
        r.raw(sz - 1)
    r.i32(); r.i32()              # linedefined, lastlinedefined
    r.byte(); r.byte(); r.byte()  # numparams, is_vararg, maxstacksize
    n = r.u32()                   # sizecode
    if n > 0x10000:
        raise ValueError("sizecode out of range - misaligned header parse")
    # decrypt=True  -> input has BGMI opcodes -> validate against BGMI_STD
    # decrypt=False -> input has STD opcodes  -> validate against STD_BGMI
    op_map = BGMI_STD if decrypt else STD_BGMI
    for _ in range(n):
        raw = r.u32()
        op = raw & 63
        if op not in op_map:
            raise ValueError(f"unsupported BGMI opcode {op}")


def _validate_bgmi_opcodes(data: bytes, decrypt: bool) -> None:
    """Scan the top-level instruction array for opcodes that have no mapping.

    Called before the key is consumed so structural errors are caught even when
    no XOR key is provided (structure-only / dry-run validation).
    Production BGMI files use a 33-byte header; some synthetic or truncated
    files use a 25-byte header (standard Lua 5.3 without LUAC_INT/LUAC_NUM).
    Try 33 first, fall back to 25 if that parse raises a structural error.
    """
    for start in (33, 25):
        try:
            _scan_opcodes_from(data, start, decrypt)
            return
        except ValueError as exc:
            if "unsupported BGMI opcode" in str(exc):
                raise          # real opcode error - propagate immediately
            if start == 25:
                raise          # both offsets failed - propagate last error
            # structural error at offset 33 - retry from 25
            continue


def is_bgmi_lua(data: bytes) -> bool:
    """True if data looks like BGMI-variant Lua 5.3 bytecode.

    BGMI signature: Lua 5.3 header with a 4-byte size_t ABI (offset 13 == 4)
    and an opcode permutation that is structurally consistent.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 34:
        return False
    data = bytes(data)
    if data[:4] != b"\x1bLua" or data[4] != 0x53:
        return False
    if data[13] != 4:
        return False
    try:
        _validate_bgmi_opcodes(data, True)
    except ValueError:
        return False
    return True


def _xor(payload: bytes, key: bytes | None) -> bytes:
    if not key:
        return payload
    klen = len(key)
    return bytes(v ^ key[i % klen] for i, v in enumerate(payload))


def transform_bgmi_lua(data: bytes, key: bytes | None = None, decrypt=True) -> bytes:
    """Convert between BGMI and standard Lua 5.3 bytecode.

    ``key`` may be empty/None for structure-only mode, in which case string
    payloads are copied unchanged instead of being XOR-decoded.
    """
    if len(data) < 34 or not data.startswith(b"\x1bLua"):
        raise ValueError("not Lua bytecode")
    # Validate opcodes before the key is required - unknown opcodes must be
    # detected and rejected regardless of whether a key was supplied.
    _validate_bgmi_opcodes(data, decrypt)

    in_width = 4 if decrypt else 8
    out_width = 8 if decrypt else 4
    r, w = _R(data), _W()
    hdr = bytearray(data[:33])
    if decrypt:
        hdr[13] = 8
    elif hdr[12:16] == b"\x04\x08\x04\x08":
        hdr[12:16] = b"\x04\x04\x04\x08"
    w.raw(hdr)
    r.p = 33
    w.byte(r.byte())          # main upvalue count

    def sread():
        sz = r.byte()
        if sz == 255:
            sz = r.sizet(in_width)
        if sz == 0:
            return None
        raw = r.raw(sz - 1)
        # Lua strings are byte sequences, not necessarily UTF-8 text. Preserve
        # them as bytes after optional XOR so both binary and textual constants
        # survive a structure conversion without replacement-character loss.
        if decrypt:
            raw = _xor(raw, key)
        return raw

    def swrite(s):
        if s is None:
            w.byte(0)
            return
        raw = s.encode("utf-8") if isinstance(s, str) else bytes(s)
        if not decrypt:
            raw = _xor(raw, key)
        sz = len(raw) + 1
        if sz < 255:
            w.byte(sz)
        else:
            w.byte(255)
            w.sizet(sz, out_width)
        w.raw(raw)

    def convert():
        swrite(sread())
        w.i32(r.i32())
        ldef = r.i32()
        w.i32(ldef)
        w.byte(r.byte()); w.byte(r.byte()); w.byte(r.byte())
        n = r.u32()
        if n > 0x10000:
            raise ValueError("sizecode out of range - misaligned header parse")
        w.u32(n)
        for _ in range(n):
            raw = r.u32()
            op = raw & 63
            A = (raw >> 6) & 255
            B = (raw >> 23) & 511
            C = (raw >> 14) & 511
            Bx = (raw >> 14) & 0x3ffff
            Ax = (raw >> 6) & 0x3ffffff
            sBx = Bx - MAXARG_sBx
            # Validate every prototype, not only the top-level code array.
            # Unknown nested opcodes must fail closed instead of being copied
            # through as if their semantics were understood.
            op_map = BGMI_STD if decrypt else STD_BGMI
            if op not in op_map:
                raise ValueError(f"unsupported BGMI opcode {op} in prototype")
            if decrypt:
                sop = op_map[op]
                if not 0 <= sop < len(STD_FMT):
                    raise ValueError(f"unsupported normalized Lua opcode {sop}")
                fmt = STD_FMT[sop]
            else:
                sop = op_map[op]
                if not 0 <= op < len(STD_FMT):
                    raise ValueError(f"unsupported standard Lua opcode {op}")
                fmt = STD_FMT[op]
            if fmt == 0:
                res = (sop & 63) | (A << 6) | (C << 14) | (B << 23)
            elif fmt == 1:
                res = (sop & 63) | (A << 6) | (Bx << 14)
            elif fmt == 2:
                res = (sop & 63) | (A << 6) | ((sBx + MAXARG_sBx) << 14)
            else:
                res = (sop & 63) | (Ax << 6)
            w.u32(res)

        nk = r.u32()
        if nk > 0x100000:
            raise ValueError("constant count out of range")
        w.u32(nk)
        for _ in range(nk):
            t = r.byte()
            w.byte(t)
            if t == 1:
                w.byte(r.byte())
            elif t in (3, 19):
                w.raw(r.raw(8))
            elif t in (4, 20):
                swrite(sread())
            else:
                raise ValueError(f"unsupported Lua 5.3 constant type {t}")

        nups = r.u32()
        if nups > 0x10000:
            raise ValueError("upvalue count out of range")
        w.u32(nups)
        for _ in range(nups):
            w.byte(r.byte()); w.byte(r.byte())

        npt = r.u32()
        if npt > 0x10000:
            raise ValueError("nested prototype count out of range")
        w.u32(npt)
        for _ in range(npt):
            convert()

        # -- debug: line info -------------------------------------------------
        nln = r.u32()
        if nln > n or nln not in (0, n):
            raise ValueError("lineinfo count does not match instruction count")
        if decrypt:
            # BGMI uses signed byte deltas plus (pc, absolute_line) checkpoints.
            # Standard Lua 5.3 stores one absolute int32 line per instruction.
            deltas = []
            for _ in range(nln):
                value = r.byte()
                deltas.append(value - 256 if value >= 128 else value)
            abs_count = r.u32()
            if abs_count > nln:
                raise ValueError("absolute line record count out of range")
            checkpoints = {}
            previous_pc = -1
            for _ in range(abs_count):
                pc, absolute_line = r.i32(), r.i32()
                if pc <= previous_pc or pc < 0 or pc >= nln or deltas[pc] != -128:
                    raise ValueError("invalid BGMI absolute line checkpoint")
                checkpoints[pc] = absolute_line
                previous_pc = pc
            w.u32(nln)
            current_line = ldef
            for pc, delta in enumerate(deltas):
                if delta == -128:
                    if pc not in checkpoints:
                        raise ValueError("missing BGMI absolute line checkpoint at pc %d" % pc)
                    current_line = checkpoints[pc]
                else:
                    current_line += delta
                w.i32(current_line)
        else:
            # Standard Lua 5.3 absolute lines -> BGMI delta/checkpoint encoding.
            lines = [r.i32() for _ in range(nln)]
            deltas = []
            checkpoints = []
            previous_line = ldef
            for pc, line in enumerate(lines):
                delta = line - previous_line
                if -127 <= delta <= 127:
                    deltas.append(delta & 0xff)
                else:
                    deltas.append(0x80)
                    checkpoints.append((pc, line))
                previous_line = line
            w.u32(nln)
            for delta in deltas:
                w.byte(delta)
            w.u32(len(checkpoints))
            for pc, line in checkpoints:
                w.i32(pc)
                w.i32(line)

        nloc = r.u32()
        if nloc > 0x100000:
            raise ValueError("local variable count out of range")
        w.u32(nloc)
        for _ in range(nloc):
            swrite(sread())
            w.i32(r.i32())
            w.i32(r.i32())

        nupn = r.u32()
        if nupn > 0x10000:
            raise ValueError("upvalue-name count out of range")
        w.u32(nupn)
        for _ in range(nupn):
            swrite(sread())

    convert()
    if r.p > len(data):
        raise ValueError("parser overrun")
    return bytes(w.b)
