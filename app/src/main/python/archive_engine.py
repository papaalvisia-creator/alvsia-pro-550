"""Unified offline PAK/OBB archive facade for ALVSIA PRO.

PAK operations delegate to the authenticated TencentPakFile core.
OBB/ZIP operations use bounded extraction and canonical-path checks.
No shell commands, network access, or automatic file discovery are used.
"""
from __future__ import annotations

import os
import stat
import tempfile
import zipfile
from pathlib import Path

MAX_ENTRIES = 50000
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_SINGLE_FILE = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000


def detect_archive(path):
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "format": "missing", "error": "input file not found"}
    try:
        with p.open("rb") as fh:
            head = fh.read(8)
        if head.startswith(b"PK\x03\x04") or zipfile.is_zipfile(str(p)):
            return {"ok": True, "format": "obb-zip", "size": p.stat().st_size}
        if len(head) >= 4:
            return {"ok": True, "format": "tencent-pak", "size": p.stat().st_size}
        return {"ok": False, "format": "unknown", "error": "file is too small"}
    except OSError as exc:
        return {"ok": False, "format": "unknown", "error": str(exc)}


def _safe_target(root, name):
    if not name or "\x00" in name or name.startswith(("/", "\\")):
        return None
    # Reject Windows drive and UNC paths even when running on Android/Linux.
    if len(name) >= 2 and name[1] == ":":
        return None
    normalized = name.replace("\\", "/")
    if any(part == ".." for part in normalized.split("/")):
        return None
    root_path = Path(root).resolve()
    target = (root_path / normalized).resolve()
    try:
        target.relative_to(root_path)
    except ValueError:
        return None
    return target


def inspect_archive(path, output_file=None):
    kind = detect_archive(path)
    if not kind.get("ok"):
        return kind
    p = Path(path)
    if kind["format"] == "obb-zip":
        try:
            with zipfile.ZipFile(str(p), "r") as zf:
                infos = zf.infolist()
                if len(infos) > MAX_ENTRIES:
                    raise ValueError("archive entry limit exceeded")
                total = sum(max(0, item.file_size) for item in infos)
                if total > MAX_TOTAL_UNCOMPRESSED:
                    raise ValueError("archive expanded-size limit exceeded")
                entries = [
                    {"name": item.filename, "size": item.file_size,
                     "compressed_size": item.compress_size, "directory": item.is_dir()}
                    for item in infos
                ]
            report = {"ok": True, "format": "obb-zip", "entries": len(entries),
                      "uncompressed_bytes": total, "items": entries}
            if output_file:
                target = Path(output_file)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    "\n".join("%s\t%s" % (x["name"], x["size"]) for x in entries),
                    encoding="utf-8",
                )
                report["out"] = str(target)
            return report
        except Exception as exc:
            return {"ok": False, "format": "obb-zip", "error": str(exc)}
    try:
        import alvsia_core as core
        return core.run_pak_list(str(p), str(output_file) if output_file else None)
    except Exception as exc:
        return {"ok": False, "format": "tencent-pak", "error": str(exc)}


def extract_archive(path, output_dir):
    kind = detect_archive(path)
    if not kind.get("ok"):
        return kind
    p = Path(path)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    if kind["format"] == "tencent-pak":
        try:
            import alvsia_core as core
            result = core.run_pak_unpack(str(p), root)
            if not isinstance(result, dict):
                return {"ok": False, "format": kind["format"], "error": "invalid PAK core response"}
            result.setdefault("format", kind["format"])
            return result
        except Exception as exc:
            return {"ok": False, "format": kind["format"], "error": str(exc)}

    written = 0
    total = 0
    seen_targets = set()
    try:
        with zipfile.ZipFile(str(p), "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ValueError("archive entry limit exceeded")
            declared_total = sum(max(0, item.file_size) for item in infos)
            if declared_total > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("archive expanded-size limit exceeded")
            for info in infos:
                target = _safe_target(root, info.filename)
                if target is None:
                    raise ValueError("unsafe archive path rejected")
                target_key = str(target)
                if target_key in seen_targets:
                    raise ValueError("duplicate archive target rejected")
                seen_targets.add(target_key)
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise ValueError("symbolic-link archive entry rejected")
                if info.file_size > MAX_SINGLE_FILE:
                    raise ValueError("archive member exceeds size limit")
                if (info.file_size >= 1024 * 1024 and info.compress_size > 0
                        and info.file_size // info.compress_size > MAX_COMPRESSION_RATIO):
                    raise ValueError("archive compression ratio exceeds limit")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temp_path = None
                try:
                    # Use a unique file in the destination directory. Never open a
                    # predictable .tmp path that could already be a symlink.
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=str(target.parent),
                        prefix="." + target.name + ".",
                        suffix=".alvsia-tmp",
                        delete=False,
                    ) as dest:
                        temp_path = Path(dest.name)
                        with zf.open(info, "r") as source:
                            copied = 0
                            while True:
                                block = source.read(1024 * 1024)
                                if not block:
                                    break
                                copied += len(block)
                                total += len(block)
                                if copied > MAX_SINGLE_FILE or total > MAX_TOTAL_UNCOMPRESSED:
                                    raise ValueError("archive expansion limit exceeded")
                                dest.write(block)
                    os.replace(str(temp_path), str(target))
                finally:
                    if temp_path is not None and temp_path.exists():
                        temp_path.unlink()
                written += 1
        return {"ok": True, "format": kind["format"], "files": written,
                "uncompressed_bytes": total, "out": str(root)}
    except Exception as exc:
        return {"ok": False, "format": kind["format"], "error": str(exc),
                "files_written_before_error": written}


def repack_obb(source_dir, output_file):
    source = Path(source_dir)
    target = Path(output_file)
    if not source.is_dir():
        return {"ok": False, "error": "source directory not found"}
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        # Create a unique temporary file rather than following a predictable
        # attacker-controlled sibling symlink.
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(target.parent),
            prefix="." + target.name + ".",
            suffix=".alvsia-tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
        with zipfile.ZipFile(str(temp_path), "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as zf:
            files = sorted(p for p in source.rglob("*") if p.is_file())
            if len(files) > MAX_ENTRIES:
                raise ValueError("source file count limit exceeded")
            total = 0
            for item in files:
                if item.is_symlink():
                    raise ValueError("symbolic-link source rejected")
                resolved = item.resolve()
                try:
                    rel = resolved.relative_to(source.resolve()).as_posix()
                except ValueError:
                    raise ValueError("source path escapes selected directory")
                size = item.stat().st_size
                total += size
                if size > MAX_SINGLE_FILE or total > MAX_TOTAL_UNCOMPRESSED:
                    raise ValueError("source size limit exceeded")
                zf.write(str(item), rel)
        os.replace(str(temp_path), str(target))
        return {"ok": True, "format": "obb-zip", "files": len(files),
                "bytes": target.stat().st_size, "out": str(target)}
    except Exception as exc:
        return {"ok": False, "format": "obb-zip", "error": str(exc)}
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def repack_pak(base_pak, modified_dir, output_pak, smart=True):
    try:
        import alvsia_core as core
        if smart:
            result = core.run_pak_smart_repack(base_pak, modified_dir, output_pak)
            if isinstance(result, dict) and result.get("ok"):
                return result
        return core.run_pak_repack(base_pak, modified_dir, output_pak)
    except Exception as exc:
        return {"ok": False, "format": "tencent-pak", "error": str(exc)}
