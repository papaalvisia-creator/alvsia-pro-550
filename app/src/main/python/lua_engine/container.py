from __future__ import annotations

from dataclasses import dataclass
import zlib

LUA_MAGIC = b"\\x1bLua"
LJ_MAGIC = b"\\x1bLJ"
_DEFLATE_INPUT_CHUNK = 64 * 1024


@dataclass(frozen=True)
class ContainerInfo:
    wrapped: bool
    format: str
    chunks: int
    output_size: int
    notes: tuple[str, ...] = ()


class _LuaContainerLimitError(ValueError):
    """Raised when an inflate operation exceeds its explicit output cap."""


def _decompress_at(data: bytes, start: int, max_output: int, wbits: int):
    """Decode one bounded zlib/raw-DEFLATE stream and return its exact end.

    The decoder's EOF/unused_data position is authoritative. Searching for a
    marker inside compressed bytes is unsafe because marker-like bytes can
    occur in the DEFLATE payload itself.
    """
    if max_output < 0:
        raise _LuaContainerLimitError("compressed Lua container exceeds output limit")
    dec = zlib.decompressobj(wbits)
    out = bytearray()
    cursor = start

    while cursor < len(data):
        block = data[cursor:cursor + _DEFLATE_INPUT_CHUNK]
        cursor += len(block)
        pending = block
        while pending:
            before = len(pending)
            part = dec.decompress(pending, max_output - len(out) + 1)
            if part:
                out.extend(part)
                if len(out) > max_output:
                    raise _LuaContainerLimitError(
                        "compressed Lua container exceeds output limit"
                    )
            pending = dec.unconsumed_tail
            if dec.eof:
                consumed = cursor - len(dec.unused_data)
                return bytes(out), consumed
            if pending and len(pending) == before and not part:
                raise ValueError("DEFLATE decoder made no progress")

    if not dec.eof:
        raise ValueError("truncated DEFLATE stream")
    return bytes(out), cursor


def _raw_deflate_at(data: bytes, start: int, max_output: int):
    """Decode one raw-DEFLATE stream after a 0x78da framing marker."""
    return _decompress_at(data, start, max_output, -15)


def unwrap_lua_container(data: bytes, max_output: int = 256 * 1024 * 1024):
    """Return (payload, ContainerInfo).

    Supports normal zlib data and the chunked 0x78da/raw-DEFLATE container
    observed in CharacterBase.lua. Chunk boundaries are taken from DEFLATE
    EOF, not from every occurrence of the byte pair 78 DA. Invalid marker
    candidates between members are skipped; output remains strictly bounded.
    """
    def _is_zlib_header(d: bytes) -> bool:
        if len(d) < 2:
            return False
        cmf, flg = d[0], d[1]
        return cmf == 0x78 and (cmf * 256 + flg) % 31 == 0

    if not _is_zlib_header(data):
        return data, ContainerInfo(False, "none", 0, len(data), ())

    # First try a normal RFC1950 zlib stream, but keep decompression bounded.
    try:
        payload, _ = _decompress_at(data, 0, max_output, 15)
        has_lua = payload.startswith((LUA_MAGIC, LJ_MAGIC))
        if not has_lua:
            # Allow only a textual comment/shebang banner before Lua magic.
            candidates = [x for x in (payload.find(LUA_MAGIC, 1, 65536),
                                       payload.find(LJ_MAGIC, 1, 65536)) if x > 0]
            for offset in sorted(candidates):
                try:
                    prefix = payload[:offset].decode("utf-8")
                except UnicodeDecodeError:
                    continue
                lines = prefix.splitlines()
                if lines and all(not line.strip() or line.lstrip().startswith(("--", "#!"))
                                 for line in lines) and not any(
                    ord(ch) < 32 and ch not in "\\t\\r\\n" for ch in prefix
                ):
                    has_lua = True
                    break
        if payload and has_lua:
            return payload, ContainerInfo(True, "zlib", 1, len(payload),
                                          ("standard zlib container",))
    except _LuaContainerLimitError:
        raise
    except (zlib.error, ValueError):
        pass

    chunks = []
    pos = 0
    total = 0
    skipped_candidates = 0
    marker_bytes = b"\\x78\\xda"

    while True:
        marker = data.find(marker_bytes, pos)
        if marker < 0:
            break
        try:
            chunk, end = _raw_deflate_at(data, marker + 2, max_output - total)
            if not chunk:
                raise ValueError("empty raw-DEFLATE member")
        except _LuaContainerLimitError:
            raise
        except (zlib.error, ValueError):
            # A 78 DA byte pair may be embedded in a separator or unrelated
            # bytes. Keep searching rather than aborting valid later members.
            skipped_candidates += 1
            pos = marker + 2
            continue

        chunks.append(chunk)
        total += len(chunk)
        if total > max_output:
            raise _LuaContainerLimitError("decompressed Lua payload exceeds output limit")

        # Resume at the exact end reported by the DEFLATE decoder. This skips
        # marker-like bytes inside the member that was just decoded.
        pos = end

    payload = b"".join(chunks)
    if not payload:
        raise ValueError("78da container contains no valid DEFLATE payload")

    notes = ["chunked raw-DEFLATE container"]
    if b"CLMM" in data[: min(len(data), 4096 * 1024)]:
        notes.append("CLMM/padding separators detected")
    if skipped_candidates:
        notes.append(f"skipped invalid 78da candidates={skipped_candidates}")
    if payload.startswith(LUA_MAGIC):
        notes.append("Lua bytecode recovered from container")
    elif payload.startswith(LJ_MAGIC):
        notes.append("LuaJIT bytecode recovered from container")
    else:
        notes.append("payload recovered but Lua magic is absent")

    return payload, ContainerInfo(True, "chunked-raw-deflate", len(chunks),
                                  len(payload), tuple(notes))
