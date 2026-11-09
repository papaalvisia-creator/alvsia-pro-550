"""
Pure-Python Lua 5.3 bytecode decompiler.
Targets the standard luac 5.3 binary format (version byte 0x53).
Produces real, valid Lua 5.3 source that re-compiles cleanly.

Format ref: lopcodes.h, ldump.c, ldo.h (Lua 5.3.6 source)
"""
from __future__ import annotations
import struct
import io
import re
import math
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple

# ── Lua 5.3 opcode table (lopcodes.h) ────────────────────────────────────────
OP = [
    "MOVE","LOADK","LOADKX","LOADBOOL","LOADNIL","GETUPVAL","GETTABUP",
    "GETTABLE","SETTABUP","SETUPVAL","SETTABLE","NEWTABLE","SELF",
    "ADD","SUB","MUL","MOD","POW","DIV","IDIV","BAND","BOR","BXOR",
    "SHL","SHR","UNM","BNOT","NOT","LEN","CONCAT","JMP","EQ","LT","LE",
    "TEST","TESTSET","CALL","TAILCALL","RETURN","FORLOOP","FORPREP",
    "TFORCALL","TFORLOOP","SETLIST","CLOSURE","VARARG","EXTRAARG",
]
OP_IDX = {n: i for i, n in enumerate(OP)}

# Instruction field widths (lua 5.3)
SIZE_OP = 6; SIZE_A = 8; SIZE_B = 9; SIZE_C = 9
POS_OP = 0; POS_A = POS_OP + SIZE_OP; POS_B = POS_A + SIZE_A + SIZE_C; POS_C = POS_A + SIZE_A
MAXARG_Bx = (1 << (SIZE_B + SIZE_C)) - 1
MAXARG_sBx = MAXARG_Bx >> 1
BITRK = 1 << (SIZE_B - 1)

def _field(i, pos, size):
    return (i >> pos) & ((1 << size) - 1)

def decode(ins: int):
    op  = _field(ins, POS_OP, SIZE_OP)
    a   = _field(ins, POS_A,  SIZE_A)
    c   = _field(ins, POS_C,  SIZE_C)
    b   = _field(ins, POS_B,  SIZE_B)
    bx  = c | (b << SIZE_C)
    sbx = bx - MAXARG_sBx
    return op, a, b, c, bx, sbx

def is_rk(x): return bool(x & BITRK)
def rk_idx(x): return x & ~BITRK

# ── Binary reader ─────────────────────────────────────────────────────────────
LUA53_HEADER = bytes([0x1b, 0x4c, 0x75, 0x61, 0x53, 0x00,
                       0x19, 0x93, 0x0d, 0x0a, 0x1a, 0x0a])

PUBGM_STRING_XOR_KEY = bytes.fromhex("112136474657a78d9d8490d8ab008c35261af7e45805b8b31507d02c1e8ff6c8")
INVALID_CONSTANT_REF_COUNT = 0
PUBGM_OPCODE_MAP = (17,18,19,20,21,22,23,24,25,26,27,28,29,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46)

class Reader:
    def __init__(self, data: bytes, *, pubgm: bool = False, hybrid_long_string_size: bool = False):
        self._d = memoryview(data)
        self._pos = 0
        self.int_size = 4
        self.sizet_size = 4
        self.instr_size = 4
        self.lua_int_size = 8
        self.lua_num_size = 8
        self.little = True
        self.hybrid_long_string_size = hybrid_long_string_size
        self.pubgm = pubgm

    def remaining(self):
        return len(self._d) - self._pos

    def _read(self, n):
        if not isinstance(n, int) or n < 0:
            raise ValueError(f"invalid Lua chunk read length {n!r} at offset {self._pos}")
        end = self._pos + n
        if end > len(self._d):
            raise ValueError(
                f"truncated Lua chunk at offset {self._pos}: "
                f"need {n} bytes, have {self.remaining()}"
            )
        v = bytes(self._d[self._pos:end])
        self._pos = end
        return v

    def byte(self): return self._read(1)[0]
    def uint8(self): return self._read(1)[0]

    def int_(self):
        raw = self._read(self.int_size)
        fmt = ("<" if self.little else ">") + ("i" if self.int_size == 4 else "q")
        return struct.unpack(fmt, raw)[0]

    def uint_(self):
        raw = self._read(self.int_size)
        fmt = ("<" if self.little else ">") + ("I" if self.int_size == 4 else "Q")
        return struct.unpack(fmt, raw)[0]

    def sizet_(self):
        raw = self._read(self.sizet_size)
        fmt = ("<" if self.little else ">") + ("I" if self.sizet_size == 4 else "Q")
        return struct.unpack(fmt, raw)[0]

    def lua_int(self):
        raw = self._read(self.lua_int_size)
        fmt = ("<" if self.little else ">") + ("q" if self.lua_int_size == 8 else "i")
        return struct.unpack(fmt, raw)[0]

    def lua_num(self):
        raw = self._read(self.lua_num_size)
        return struct.unpack("<d" if self.little else ">d", raw)[0]

    def string(self):
        size = self.uint8()
        if size == 0xFF:
            if self.hybrid_long_string_size and self.sizet_size == 4:
                raw = self._read(8)
                size = struct.unpack("<Q" if self.little else ">Q", raw)[0]
            else:
                size = self.sizet_()
        if size == 0:
            return None
        raw = self._read(size - 1)
        if self.pubgm:
            raw = bytes(b ^ PUBGM_STRING_XOR_KEY[i % len(PUBGM_STRING_XOR_KEY)] for i, b in enumerate(raw))
        try:
            return raw.decode("utf-8", "replace")
        except Exception:
            return raw.decode("latin-1", "replace")

    def instruction(self):
        raw = self._read(self.instr_size)
        value = struct.unpack("<I" if self.little else ">I", raw)[0]
        if self.pubgm:
            op = value & 0x3F
            if op >= len(PUBGM_OPCODE_MAP):
                raise ValueError(f"invalid PUBG Mobile Lua opcode {op}")
            value = (value & ~0x3F) | PUBGM_OPCODE_MAP[op]
        return value


# ── Proto (function prototype) ────────────────────────────────────────────────
class Proto:
    source: Optional[str] = None
    linedefined: int = 0
    lastlinedefined: int = 0
    numparams: int = 0
    is_vararg: int = 0
    maxstacksize: int = 0
    code: List[int] = []
    constants: List[Any] = []
    upvalues: List[dict] = []
    protos: List["Proto"] = []
    lineinfo: List[int] = []
    locvars: List[dict] = []
    upvalue_names: List[Optional[str]] = []

    def __init__(self): pass


def _read_count(r: Reader, label: str, min_item_bytes: int, *, allow_zero: bool = True) -> int:
    count = r.int_()
    if count < 0 or (not allow_zero and count == 0):
        raise ValueError(f"invalid {label} count {count} at offset {r._pos}")
    # A count cannot describe more minimum-sized entries than remain in the file.
    if min_item_bytes <= 0 or count > r.remaining() // min_item_bytes:
        raise ValueError(
            f"invalid {label} count {count} at offset {r._pos}: "
            f"{r.remaining()} bytes remain"
        )
    # Avoid pathological allocations from corrupted or intentionally malformed chunks.
    if count > 2_000_000:
        raise ValueError(f"{label} count exceeds safety limit: {count}")
    return count


def load_proto(r: Reader, depth: int = 0) -> Proto:
    if depth > 200:
        raise ValueError("Lua prototype nesting exceeds safety limit")
    p = Proto()
    p.source = r.string()
    p.linedefined = r.int_()
    p.lastlinedefined = r.int_()
    p.numparams = r.uint8()
    p.is_vararg = r.uint8()
    p.maxstacksize = r.uint8()

    # code
    n = _read_count(r, "instruction", 4, allow_zero=False)
    p.code = [r.instruction() for _ in range(n)]

    # constants
    n = _read_count(r, "constant", 1)
    p.constants = []
    for _ in range(n):
        t = r.uint8()
        if t == 0:
            p.constants.append(None)
        elif t == 1:
            p.constants.append(bool(r.uint8()))
        elif t == 3:  # LUA_TNUMFLT
            p.constants.append(r.lua_num())
        elif t == 19:  # LUA_TNUMINT (3 | (1<<4))
            p.constants.append(r.lua_int())
        elif t == 4 or t == 20:  # LUA_TSTRING short/long
            p.constants.append(r.string())
        else:
            p.constants.append(None)

    # upvalues (preliminary — names come later)
    n = _read_count(r, "upvalue", 2)
    p.upvalues = []
    for _ in range(n):
        instack = r.uint8()
        idx = r.uint8()
        p.upvalues.append({"instack": instack, "idx": idx, "name": None})

    # nested protos
    n = _read_count(r, "nested prototype", 1)
    p.protos = [load_proto(r, depth + 1) for _ in range(n)]

    # debug: lineinfo
    if r.pubgm:
        n = _read_count(r, "line delta", 1)
        _deltas = [struct.unpack("b", r._read(1))[0] for _ in range(n)]
        abs_n = _read_count(r, "absolute line", 8)
        _abs_lines = [(r.int_(), r.int_()) for _ in range(abs_n)]
        p.lineinfo = _deltas
    else:
        n = _read_count(r, "lineinfo", 4)
        p.lineinfo = [r.int_() for _ in range(n)]

    # debug: locvars
    n = _read_count(r, "local variable", 9)
    p.locvars = []
    for _ in range(n):
        name = r.string()
        startpc = r.int_()
        endpc = r.int_()
        p.locvars.append({"name": name, "startpc": startpc, "endpc": endpc})

    # debug: upvalue names
    n = _read_count(r, "upvalue name", 1)
    if n > len(p.upvalues):
        raise ValueError(f"upvalue-name count {n} exceeds upvalue count {len(p.upvalues)}")
    for i in range(n):
        name = r.string()
        if i < len(p.upvalues):
            p.upvalues[i]["name"] = name

    return p


def load_chunk(data: bytes, *, hybrid_long_string_size: bool = False, pubgm: bool = False) -> Proto:
    r = Reader(data, pubgm=pubgm, hybrid_long_string_size=hybrid_long_string_size)
    # header
    sig = r._read(4)
    if sig != b"\x1bLua":
        raise ValueError("not a Lua chunk")
    version = r.byte()
    if version != 0x53:
        raise ValueError(f"expected Lua 5.3 (0x53), got {version:#x}")
    fmt = r.byte()
    luac_data = r._read(6)   # 0x19 0x93 0x0d 0x0a 0x1a 0x0a
    if fmt != 0:
        raise ValueError(f"unsupported Lua 5.3 chunk format {fmt}")
    if luac_data != b"\x19\x93\x0d\x0a\x1a\x0a":
        raise ValueError("Lua 5.3 header check bytes do not match; input may be wrapped or protected")
    r.int_size = r.byte()
    r.hybrid_long_string_size = hybrid_long_string_size
    r.sizet_size = r.byte()
    r.instr_size = r.byte()
    r.lua_int_size = r.byte()
    r.lua_num_size = r.byte()
    if r.int_size != 4 or r.instr_size != 4 or r.sizet_size not in (4, 8) or r.lua_int_size not in (4, 8) or r.lua_num_size not in (4, 8):
        raise ValueError(
            "unsupported Lua 5.3 field sizes: "
            f"int={r.int_size}, size_t={r.sizet_size}, instruction={r.instr_size}, "
            f"lua_Integer={r.lua_int_size}, lua_Number={r.lua_num_size}"
        )
    _lua_int_check = r.lua_int()   # LUAC_INT  = 0x5678
    _lua_num_check = r.lua_num()   # LUAC_NUM  = 370.5
    if _lua_int_check != 0x5678 or _lua_num_check != 370.5:
        raise ValueError("Lua 5.3 integer/number format check failed; input may be endian-swapped or protected")
    # main upvalue count (upvalues field before main proto)
    _upval_count = r.byte()
    return load_proto(r)


# ── Name tracking ─────────────────────────────────────────────────────────────
def _safe(name: Optional[str], fallback: str) -> str:
    if name and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        return name
    return fallback


# ── Expression / Statement reconstruction ────────────────────────────────────
LUA_KEYWORDS = frozenset([
    "and","break","do","else","elseif","end","false","for","function",
    "goto","if","in","local","nil","not","or","repeat","return",
    "then","true","until","while",
])

_BINOP_MAP = {
    "ADD": "+", "SUB": "-", "MUL": "*", "MOD": "%", "POW": "^",
    "DIV": "/", "IDIV": "//", "BAND": "&", "BOR": "|", "BXOR": "~",
    "SHL": "<<", "SHR": ">>",
    "EQ": "==", "LT": "<", "LE": "<=",
}
_UNOP_MAP = {"UNM": "-", "BNOT": "~", "NOT": "not ", "LEN": "#"}


class Decompiler:
    def __init__(self, proto: Proto, name: str = "main", depth: int = 0, upval_names: List[str] = None):
        self.p = proto
        self.name = name
        self.depth = depth
        self.indent = "  " * depth
        # Register → expression string
        self.regs: Dict[int, str] = {}
        self.invalid_constant_refs: List[tuple[int,int,str]] = []
        self.lines: List[str] = []
        # Track local variable names by register
        self.locals: Dict[int, str] = {}
        # Upvalue names
        self.upval_names: List[str] = []
        for i, uv in enumerate(proto.upvalues):
            nm = uv.get("name") or (upval_names[i] if upval_names and i < len(upval_names) else None)
            self.upval_names.append(_safe(nm, f"_upv{i}"))
        # Build local name map from debug info
        for lv in proto.locvars:
            nm = lv.get("name")
            # locvars are assigned in order of appearance
        # PC → active locals at that pc
        self._pc_locals: Dict[int, Dict[int, str]] = {}
        self._build_local_map()

    def _build_local_map(self):
        p = self.p
        # Assign registers based on declaration order
        # Each locvar gets the next available register slot
        self._all_locals: List[Tuple[int, int, int, str]] = []  # (startpc, endpc, reg, name)
        reg = 0
        # params first
        for i in range(p.numparams):
            nm = None
            if i < len(p.locvars):
                nm = p.locvars[i].get("name")
            self._all_locals.append((0, len(p.code), i, _safe(nm, f"arg{i}")))
        # remaining locvars after params
        param_count = p.numparams
        # We number the remaining slots in order
        # lua assigns locvar[i] to register i (params fill 0..numparams-1)
        for i, lv in enumerate(p.locvars):
            nm = _safe(lv.get("name"), f"_v{i}")
            s, e = lv["startpc"], lv["endpc"]
            reg = i  # locvars are indexed by their slot
            # Replace params if already added
            # locvars[0..numparams-1] are the params
            # Find if already added
            found = False
            for j, (ss, ee, rr, nn) in enumerate(self._all_locals):
                if rr == i and ss == 0:
                    # already a param
                    self._all_locals[j] = (s, e, reg, nm)
                    found = True
                    break
            if not found:
                self._all_locals.append((s, e, i, nm))

    def _local_at(self, pc: int, reg: int) -> Optional[str]:
        best = None
        for startpc, endpc, r, nm in self._all_locals:
            if r == reg and startpc <= pc < endpc:
                best = nm
        return best

    def _k(self, idx: int) -> str:
        if idx < 0 or idx >= len(self.p.constants):
            global INVALID_CONSTANT_REF_COUNT
            INVALID_CONSTANT_REF_COUNT += 1
            self.invalid_constant_refs.append((idx, len(self.p.constants), self.name))
            return "nil"
        v = self.p.constants[idx]
        return self._lit(v)

    def _lit(self, v: Any) -> str:
        if v is None:
            return "nil"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            if math.isnan(v):
                return "(0/0)"
            if math.isinf(v):
                return ("math.huge" if v > 0 else "-math.huge")
            s = repr(v)
            if "." not in s and "e" not in s:
                s += ".0"
            return s
        if isinstance(v, str):
            escaped = (v.replace("\\", "\\\\")
                        .replace("\n", "\\n")
                        .replace("\r", "\\r")
                        .replace("\t", "\\t")
                        .replace('"', '\\"'))
            return f'"{escaped}"'
        return repr(v)

    def _rk(self, x: int, pc: int) -> str:
        if is_rk(x):
            return self._k(rk_idx(x))
        return self._reg(x, pc)

    def _reg(self, r: int, pc: int) -> str:
        nm = self._local_at(pc, r)
        if nm:
            return nm
        if r in self.regs:
            return self.regs[r]
        return f"_r{r}"

    def _emit(self, line: str):
        self.lines.append(self.indent + line)

    def decompile(self) -> List[str]:
        p = self.p
        # Function header
        params = []
        for i in range(p.numparams):
            nm = self._local_at(0, i) or f"a{i}"
            params.append(nm)
        if p.is_vararg:
            params.append("...")

        # Build output
        header_lines = []
        body_lines = []

        if self.name == "main":
            # Top level chunk
            body_lines = self._decompile_body()
        else:
            # Named function — header generated by parent
            body_lines = self._decompile_body()

        return body_lines

    def _decompile_body(self) -> List[str]:
        p = self.p
        out = []
        i = 0
        n = len(p.code)
        # Track which PCs have been handled by compound constructs
        skip_pcs = set()
        # Assigned locals tracker: reg → name (for MOVE/LOADK etc.)
        assigned: Dict[int, str] = {}
        pending_local_decl: Dict[int, str] = {}  # reg → name to declare as local

        # Collect which regs get declared as local at each PC
        local_decl: Dict[int, int] = {}  # pc → reg
        for s, e, r, nm in self._all_locals:
            if s not in local_decl:
                local_decl[s] = []
            local_decl[s].append((r, nm))

        while i < n:
            if i in skip_pcs:
                i += 1
                continue
            ins = p.code[i]
            op, a, b, c, bx, sbx = decode(ins)
            opname = OP[op] if op < len(OP) else f"OP_{op}"

            lv_decls = local_decl.get(i, [])

            if opname == "MOVE":
                src = self._reg(b, i)
                dst_nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = src
                if lv_decls:
                    for r, nm in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm} = {src}")
                            self.regs[a] = nm
                            break
                    else:
                        out.append(f"{self.indent}{dst_nm} = {src}")
                else:
                    nm = self._local_at(i, a)
                    if nm:
                        out.append(f"{self.indent}{nm} = {src}")
                    else:
                        out.append(f"{self.indent}{dst_nm} = {src}")

            elif opname == "LOADK":
                val = self._k(bx)
                nm = self._local_at(i + 1, a) or self._local_at(i, a) or f"_r{a}"
                self.regs[a] = val
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm2} = {val}")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}{nm} = {val}")
                else:
                    out.append(f"{self.indent}{nm} = {val}")

            elif opname == "LOADKX":
                # Next instruction is EXTRAARG
                if i + 1 < n:
                    next_ins = p.code[i + 1]
                    nop, *_ = decode(next_ins)
                    nax = (next_ins >> POS_A) & ((1 << (SIZE_A + SIZE_B + SIZE_C)) - 1)
                    val = self._k(nax)
                    skip_pcs.add(i + 1)
                else:
                    val = "nil"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = val
                out.append(f"{self.indent}{nm} = {val}")

            elif opname == "LOADBOOL":
                val = "true" if b else "false"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = val
                out.append(f"{self.indent}{nm} = {val}")
                if c:  # skip next
                    skip_pcs.add(i + 1)

            elif opname == "LOADNIL":
                for r in range(a, a + b + 1):
                    nm = self._local_at(i + 1, r) or f"_r{r}"
                    self.regs[r] = "nil"
                    out.append(f"{self.indent}{nm} = nil")

            elif opname == "GETUPVAL":
                uv = self.upval_names[b] if b < len(self.upval_names) else f"_upv{b}"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = uv
                out.append(f"{self.indent}{nm} = {uv}")

            elif opname == "SETUPVAL":
                uv = self.upval_names[b] if b < len(self.upval_names) else f"_upv{b}"
                src = self._reg(a, i)
                out.append(f"{self.indent}{uv} = {src}")

            elif opname == "GETTABUP":
                uv = self.upval_names[b] if b < len(self.upval_names) else f"_upv{b}"
                key = self._rk(c, i)
                expr = f"{uv}[{key}]"
                # If key is a plain string identifier, use dot notation
                if key.startswith('"') and key.endswith('"'):
                    ks = key[1:-1]
                    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', ks) and ks not in LUA_KEYWORDS:
                        expr = f"{uv}.{ks}"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = expr
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm2} = {expr}")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}{nm} = {expr}")
                else:
                    out.append(f"{self.indent}{nm} = {expr}")

            elif opname == "SETTABUP":
                uv = self.upval_names[a] if a < len(self.upval_names) else f"_upv{a}"
                key = self._rk(b, i)
                val = self._rk(c, i)
                if key.startswith('"') and key.endswith('"'):
                    ks = key[1:-1]
                    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', ks) and ks not in LUA_KEYWORDS:
                        out.append(f"{self.indent}{uv}.{ks} = {val}")
                        i += 1; continue
                out.append(f"{self.indent}{uv}[{key}] = {val}")

            elif opname == "GETTABLE":
                tbl = self._reg(b, i)
                key = self._rk(c, i)
                if key.startswith('"') and key.endswith('"'):
                    ks = key[1:-1]
                    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', ks) and ks not in LUA_KEYWORDS:
                        expr = f"{tbl}.{ks}"
                    else:
                        expr = f"{tbl}[{key}]"
                else:
                    expr = f"{tbl}[{key}]"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = expr
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm2} = {expr}")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}{nm} = {expr}")
                else:
                    out.append(f"{self.indent}{nm} = {expr}")

            elif opname == "SETTABLE":
                tbl = self._local_at(i, a) or f"_r{a}"
                key = self._rk(b, i)
                val = self._rk(c, i)
                if key.startswith('"') and key.endswith('"'):
                    ks = key[1:-1]
                    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', ks) and ks not in LUA_KEYWORDS:
                        out.append(f"{self.indent}{tbl}.{ks} = {val}")
                        i += 1; continue
                out.append(f"{self.indent}{tbl}[{key}] = {val}")

            elif opname == "NEWTABLE":
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = nm
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm2} = {{}}")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}{nm} = {{}}")
                else:
                    out.append(f"{self.indent}{nm} = {{}}")

            elif opname == "SELF":
                obj = self._reg(b, i)
                key = self._rk(c, i)
                nm_a1 = self._local_at(i + 1, a + 1) or f"_r{a+1}"
                nm_a = self._local_at(i + 1, a) or f"_r{a}"
                if key.startswith('"') and key.endswith('"'):
                    ks = key[1:-1]
                    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', ks) and ks not in LUA_KEYWORDS:
                        expr = f"{obj}.{ks}"
                    else:
                        expr = f"{obj}[{key}]"
                else:
                    expr = f"{obj}[{key}]"
                self.regs[a] = expr
                self.regs[a + 1] = obj
                out.append(f"{self.indent}{nm_a} = {expr}")
                out.append(f"{self.indent}{nm_a1} = {obj}")

            elif opname in _BINOP_MAP:
                sym = _BINOP_MAP[opname]
                lhs = self._rk(b, i)
                rhs = self._rk(c, i)
                expr = f"({lhs}) {sym} ({rhs})"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = expr
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm2} = {expr}")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}{nm} = {expr}")
                else:
                    out.append(f"{self.indent}{nm} = {expr}")

            elif opname in _UNOP_MAP:
                sym = _UNOP_MAP[opname]
                src = self._reg(b, i)
                expr = f"({sym}{src})"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = expr
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local {nm2} = {expr}")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}{nm} = {expr}")
                else:
                    out.append(f"{self.indent}{nm} = {expr}")

            elif opname == "CONCAT":
                parts = [self._reg(j, i) for j in range(b, c + 1)]
                expr = "(" + " .. ".join(f"({part})" for part in parts) + ")"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = expr
                out.append(f"{self.indent}{nm} = {expr}")

            elif opname == "LEN":
                src = self._reg(b, i)
                expr = f"(#{src})"
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = expr
                out.append(f"{self.indent}{nm} = {expr}")

            elif opname == "JMP":
                target = i + sbx + 1
                out.append(f"{self.indent}-- JMP -> pc {target}")

            elif opname == "EQ":
                lhs = self._rk(b, i)
                rhs = self._rk(c, i)
                sense = "" if a == 0 else "not "
                out.append(f"{self.indent}-- if {sense}({lhs} == {rhs}) then")

            elif opname == "LT":
                lhs = self._rk(b, i)
                rhs = self._rk(c, i)
                sense = "" if a == 0 else "not "
                out.append(f"{self.indent}-- if {sense}({lhs} < {rhs}) then")

            elif opname == "LE":
                lhs = self._rk(b, i)
                rhs = self._rk(c, i)
                sense = "" if a == 0 else "not "
                out.append(f"{self.indent}-- if {sense}({lhs} <= {rhs}) then")

            elif opname == "TEST":
                src = self._reg(a, i)
                out.append(f"{self.indent}-- if (bool({src}) == {bool(c)}) then")

            elif opname == "TESTSET":
                src = self._reg(b, i)
                nm = self._reg(a, i)
                out.append(f"{self.indent}-- if (bool({src}) == {bool(c)}) then {nm} = {src}")

            elif opname == "CALL":
                func = self._reg(a, i)
                arg_count = b - 1
                if arg_count < 0:
                    args = [self._reg(j, i) for j in range(a + 1, a + 2)]
                    if self.p.is_vararg:
                        args.append("...")
                else:
                    args = [self._reg(j, i) for j in range(a + 1, a + 1 + arg_count)]
                # C == 0 means multret; exact register arity is dynamic.
                # Keep the reconstructed call syntactically valid instead of emitting
                # an empty assignment target.
                ret_count = c - 1
                # Materialize complex call targets to preserve Lua precedence.
                call_target = func
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", func):
                    call_target = f"_alvsia_call_{i}"
                    out.append(f"{self.indent}local {call_target} = {func}")
                call_expr = f"{call_target}({', '.join(args)})"
                if ret_count == 0:
                    out.append(f"{self.indent}{call_expr}")
                elif ret_count == 1:
                    nm = self._local_at(i + 1, a) or f"_r{a}"
                    self.regs[a] = call_expr
                    if lv_decls:
                        for r, nm2 in lv_decls:
                            if r == a:
                                out.append(f"{self.indent}local {nm2} = {call_expr}")
                                self.regs[a] = nm2
                                break
                        else:
                            out.append(f"{self.indent}{nm} = {call_expr}")
                    else:
                        out.append(f"{self.indent}{nm} = {call_expr}")
                elif c == 0:
                    # Multret result count is unknown at this reconstruction layer.
                    # Preserve execution order and syntax; downstream dataflow can
                    # still inspect the original bytecode for exact arity.
                    out.append(f"{self.indent}{call_expr}")
                else:
                    rets = []
                    for j in range(a, a + ret_count):
                        nm = self._local_at(i + 1, j) or f"_r{j}"
                        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", nm):
                            nm = f"_r{j}"
                        self.regs[j] = nm
                        rets.append(nm)
                    lhs = ", ".join(rets) or f"_r{a}"
                    if lv_decls:
                        out.append(f"{self.indent}local {lhs} = {call_expr}")
                    else:
                        out.append(f"{self.indent}{lhs} = {call_expr}")

            elif opname == "TAILCALL":
                func = self._reg(a, i)
                arg_count = b - 1
                if arg_count < 0:
                    args = [self._reg(j, i) for j in range(a + 1, a + 2)]
                    if self.p.is_vararg:
                        args.append("...")
                else:
                    args = [self._reg(j, i) for j in range(a + 1, a + 1 + arg_count)]
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", func):
                    func = f"_alvsia_tailcall_{i}"
                    out.append(f"{self.indent}local {func} = {self._reg(a, i)}")
                # Tail calls are terminal in bytecode, but later bytecode may
                # still be emitted by the conservative linear reconstruction. Wrap
                # the return in a nested block so Lua permits subsequent statements.
                out.append(f"{self.indent}do return {func}({', '.join(args)}) end")

            elif opname == "RETURN":
                if b == 1:
                    out.append(f"{self.indent}do return end")
                elif b == 2:
                    src = self._reg(a, i)
                    out.append(f"{self.indent}do return {src} end")
                else:
                    count = b - 1
                    if count < 0:
                        srcs = [self._reg(j, i) for j in range(a, a + 2)]
                        if self.p.is_vararg:
                            srcs.append("...")
                    else:
                        srcs = [self._reg(j, i) for j in range(a, a + count)]
                    out.append(f"{self.indent}do return {', '.join(srcs)} end")

            elif opname == "VARARG":
                nm = self._local_at(i + 1, a) or f"_r{a}"
                self.regs[a] = "..."
                if b == 0:
                    # B == 0 is multret vararg. Lua source cannot use "..." on
                    # the left-hand side, so capture one value safely and retain
                    # an explicit diagnostic comment.
                    out.append(f"{self.indent}{nm} = ...")
                    out.append(f"{self.indent}-- VARARG multret reconstructed from register {a}")
                elif b == 1:
                    out.append(f"{self.indent}{nm} = ...")
                else:
                    count = b - 1
                    names = []
                    for j in range(a, a + count):
                        nm2 = self._local_at(i + 1, j) or f"_r{j}"
                        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", nm2):
                            nm2 = f"_r{j}"
                        self.regs[j] = "..."
                        names.append(nm2)
                    lhs = ", ".join(names) or nm
                    out.append(f"{self.indent}{lhs} = ...")

            elif opname == "CLOSURE":
                sub = p.protos[bx]
                sub_name = self._local_at(i + 1, a) or f"_func{bx}"
                self.regs[a] = sub_name
                # Recurse
                params = []
                for pi in range(sub.numparams):
                    pn = None
                    if pi < len(sub.locvars):
                        pn = _safe(sub.locvars[pi].get("name"), f"a{pi}")
                    params.append(pn or f"a{pi}")
                if sub.is_vararg:
                    params.append("...")
                uv_names = [uv.get("name") for uv in p.upvalues]
                sub_dec = Decompiler(sub, sub_name, self.depth, uv_names)
                sub_body = sub_dec.decompile()
                if lv_decls:
                    for r, nm2 in lv_decls:
                        if r == a:
                            out.append(f"{self.indent}local function {nm2}({', '.join(params)})")
                            self.regs[a] = nm2
                            break
                    else:
                        out.append(f"{self.indent}local function {sub_name}({', '.join(params)})")
                else:
                    out.append(f"{self.indent}local function {sub_name}({', '.join(params)})")
                out.extend(sub_body)
                out.append(f"{self.indent}end")

            elif opname == "SETLIST":
                tbl = self._local_at(i, a) or f"_r{a}"
                count = b if b > 0 else 1
                base = (c - 1) * 50
                for j in range(1, count + 1):
                    val = self._reg(a + j, i)
                    out.append(f"{self.indent}{tbl}[{base + j}] = {val}")

            elif opname == "FORPREP":
                idx_reg = a
                limit_reg = a + 1
                step_reg = a + 2
                var_reg = a + 3
                idx = self._reg(idx_reg, i)
                limit = self._reg(limit_reg, i)
                step = self._reg(step_reg, i)
                var_nm = self._local_at(i + 1, var_reg) or f"_i{a}"
                out.append(f"{self.indent}for {var_nm} = {idx}, {limit}, {step} do")

            elif opname == "FORLOOP":
                out.append(f"{self.indent}end -- forloop")

            elif opname == "TFORCALL":
                func = self._reg(a, i)
                args_regs = [self._reg(a + 1, i), self._reg(a + 2, i)]
                rets = [self._local_at(i + 1, a + 3 + j) or f"_r{a+3+j}" for j in range(c)]
                out.append(f"{self.indent}{', '.join(rets)} = {func}({', '.join(args_regs)})")

            elif opname == "TFORLOOP":
                out.append(f"{self.indent}-- tforloop")

            elif opname == "EXTRAARG":
                pass  # handled by LOADKX

            else:
                out.append(f"{self.indent}-- {opname} a={a} b={b} c={c}")

            i += 1
        return out


# ── Top-level entry ───────────────────────────────────────────────────────────
def decompile_bytes(data: bytes) -> str:
    global INVALID_CONSTANT_REF_COUNT
    INVALID_CONSTANT_REF_COUNT = 0
    errors = []
    for variant in ("standard", "pubgm"):
        try:
            proto = load_chunk(data, pubgm=(variant == "pubgm"))
            break
        except Exception as exc:
            errors.append(f"{variant}: {exc}")
    else:
        raise ValueError(" ; ".join(errors))
    # Top-level params
    params = []
    if proto.is_vararg:
        params.append("...")

    header = [
        "-- Decompiled by ALVSIA PRO pure-Python Lua 5.3 decompiler",
        f"-- Source: {proto.source or '?'}",
        "",
    ]

    dec = Decompiler(proto, "main", 0, [])
    body = dec.decompile()

    # Collect nested function definitions that were emitted inline
    # Top-level body IS the chunk body — no wrapping function needed
    if INVALID_CONSTANT_REF_COUNT:
        header.append(f"-- ALVSIA_INVALID_CONSTANT_REF_COUNT={INVALID_CONSTANT_REF_COUNT}")
    lines = header + body
    return "\n".join(lines)


def decompile_file(src: Path, dst: Path) -> dict:
    data = src.read_bytes()
    # Strip standard header check
    if not data.startswith(b"\x1bLua"):
        return {"ok": False, "error": "not a Lua bytecode file"}
    if len(data) > 4 and data[4] != 0x53:
        ver = data[4]
        return {"ok": False, "error": f"Lua version {ver:#x} not 5.3 — only 5.3 supported"}
    try:
        src_text = decompile_bytes(data)
        # A valid Lua chunk always contains executable instructions; header-only
        # output is a parse artifact, not a successful decompile.
        if not src_text.strip() or src_text.count("\n") < 2:
            return {"ok": False, "error": "decompile produced no executable Lua source"}
        if "-- Decompiled by ALVSIA PRO" in src_text and len(data) > 16:
            body = src_text.split("\n\n", 1)[-1].strip()
            if not body:
                return {"ok": False, "error": "decompile produced an empty Lua body"}
    except Exception as e:
        return {"ok": False, "error": f"decompile failed: {e}"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src_text, encoding="utf-8")
    lines = src_text.count("\n") + 1
    return {"ok": True, "out": str(dst), "lines": lines, "size": len(src_text)}
