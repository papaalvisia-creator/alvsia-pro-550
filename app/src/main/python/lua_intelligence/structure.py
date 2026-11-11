from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class BytecodeStructure:
    dialect: str
    valid_header: bool
    header_size: int
    size: int
    sections: tuple[str, ...]
    anomalies: tuple[str, ...]
    score: float
    version: str = "unknown"
    format_byte: int | None = None
    endianness: int | None = None
    int_size: int | None = None
    size_t_size: int | None = None
    instruction_size: int | None = None
    lua_integer_size: int | None = None
    lua_number_size: int | None = None
    integral_flag: int | None = None
    payload_offset: int = 0


def _lua_header(head: bytes) -> tuple[int, list[str], dict]:
    """Parse the common Lua 5.x binary header without decoding instructions."""
    anomalies: list[str] = []
    meta: dict = {}
    if len(head) < 12:
        return 0, ["truncated-lua-header"], meta

    version_byte = head[4]
    version = f"Lua 5.{version_byte - 0x50}" if 0x51 <= version_byte <= 0x5f else f"0x{version_byte:02x}"
    meta["version"] = version
    meta["format_byte"] = head[5]
    meta["endianness"] = head[6]
    meta["int_size"] = head[7]
    meta["size_t_size"] = head[8]
    meta["instruction_size"] = head[9]
    meta["lua_integer_size"] = head[10]
    meta["lua_number_size"] = head[11]

    if head[5] != 0:
        anomalies.append("noncanonical-format")
    if head[6] not in (0, 1):
        anomalies.append("invalid-endianness")
    if head[7] not in (4, 8):
        anomalies.append("unexpected-int-size")
    if head[8] not in (4, 8):
        anomalies.append("unexpected-size_t-size")
    if head[9] != 4:
        anomalies.append("unexpected-instruction-size")
    if head[10] not in (4, 8):
        anomalies.append("unexpected-lua-integer-size")
    if head[11] not in (4, 8):
        anomalies.append("unexpected-lua-number-size")

    # Lua 5.3+ embeds LUAC_INT and LUAC_NUM in the canonical header.
    payload_offset = 12
    if version_byte >= 0x53:
        payload_offset = 33
        if len(head) < payload_offset:
            anomalies.append("truncated-extended-lua-header")
        else:
            meta["luac_int_probe"] = head[12:20].hex()
            meta["luac_num_probe"] = head[20:28].hex()
            meta["integral_flag"] = head[28] if len(head) > 28 else None
            # Bytes 29-32 are reserved/part of the implementation-specific
            # check area in some Lua-family forks; retain them as provenance.
            meta["header_tail"] = head[28:33].hex()

    return payload_offset, anomalies, meta


def analyze_bytecode_structure(path: Path, dialect="unknown") -> BytecodeStructure:
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as f:
        head = f.read(256)

    sections: list[str] = []
    anomalies: list[str] = []
    valid = False
    header_size = 0
    version = "unknown"
    meta: dict = {}

    if head.startswith(b"\x1bLua"):
        valid = True
        sections.append("puc-lua-header")
        header_size, lua_anomalies, meta = _lua_header(head)
        anomalies.extend(lua_anomalies)
        version = meta.get("version", "unknown")
        if header_size == 0:
            header_size = 12
    elif head.startswith(b"\x1bLJ"):
        valid = True
        header_size = 3
        version = "LuaJIT"
        sections.append("luajit-header")
        if size < 3:
            anomalies.append("truncated-header")
    elif head.startswith(b"Luau"):
        valid = True
        header_size = 4
        version = "Luau"
        sections.append("luau-header")
        if size < 4:
            anomalies.append("truncated-header")
    else:
        anomalies.append("canonical-bytecode-header-missing")

    if size < header_size:
        anomalies.append("file-shorter-than-header")
    if valid and size == header_size:
        anomalies.append("header-without-payload")
    if valid and header_size and size > header_size:
        sections.append("bytecode-payload")

    score = 0.0 if not valid else max(
        0.0, min(1.0, 0.95 - 0.08 * len(anomalies))
    )
    return BytecodeStructure(
        dialect=dialect,
        valid_header=valid,
        header_size=header_size,
        size=size,
        sections=tuple(sections),
        anomalies=tuple(anomalies),
        score=score,
        version=version,
        format_byte=meta.get("format_byte"),
        endianness=meta.get("endianness"),
        int_size=meta.get("int_size"),
        size_t_size=meta.get("size_t_size"),
        instruction_size=meta.get("instruction_size"),
        lua_integer_size=meta.get("lua_integer_size"),
        lua_number_size=meta.get("lua_number_size"),
        integral_flag=meta.get("integral_flag"),
        payload_offset=header_size,
    )


def structure_dict(s):
    return asdict(s)
