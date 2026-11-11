#!/usr/bin/env python3
"""Normalise APK native-library packaging so the APK is installable.

Android requires that, when ``android:extractNativeLibs="false"`` (the AGP
default for minSdk >= 23), *every* ``lib/<abi>/*.so`` entry is stored
uncompressed and page-aligned. A third-party packer that rewrites a subset of
the native libraries with DEFLATE produces a mixed-compression APK that the
package manager rejects with INSTALL_FAILED_INVALID_APK ("paket tidak valid").

This tool rewrites the archive so that every ``lib/**/*.so`` entry is STORED,
leaving all other entries untouched (same order, same compression method, same
content, same timestamps). It never adds, removes or renames an entry, and it
never touches the manifest, resources or DEX payloads.

Usage:
    normalize_apk_packaging.py <input.apk> <output.apk>
    normalize_apk_packaging.py --check <apk>
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

NATIVE_PREFIX = "lib/"


def _is_native_lib(name: str) -> bool:
    return name.startswith(NATIVE_PREFIX) and name.endswith(".so")


def native_lib_violations(apk: str | Path) -> list[str]:
    """Return human-readable packaging violations for native libraries."""
    problems: list[str] = []
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            if not _is_native_lib(info.filename):
                continue
            if info.compress_type != zipfile.ZIP_STORED:
                problems.append(
                    f"{info.filename}: compressed (method {info.compress_type}); "
                    "extractNativeLibs=false requires STORED"
                )
    return problems


def normalize(apk: str | Path, out: str | Path) -> int:
    """Rewrite *apk* into *out* with all native libraries STORED.

    Returns the number of entries whose compression method was changed.
    """
    src = Path(apk)
    dst = Path(out)
    if not src.is_file():
        raise SystemExit(f"ERROR: input APK not found: {src}")

    changed = 0
    with zipfile.ZipFile(src) as zin:
        # Write to a sibling temp file so a failure cannot leave a truncated APK.
        with tempfile.NamedTemporaryFile(
            dir=str(dst.parent or "."), prefix=".normalize-", suffix=".apk", delete=False
        ) as handle:
            tmp_name = handle.name
        try:
            with zipfile.ZipFile(tmp_name, "w", allowZip64=True) as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    method = info.compress_type
                    if _is_native_lib(info.filename) and method != zipfile.ZIP_STORED:
                        method = zipfile.ZIP_STORED
                        changed += 1
                    new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    new_info.compress_type = method
                    new_info.external_attr = info.external_attr
                    new_info.internal_attr = info.internal_attr
                    new_info.create_system = info.create_system
                    new_info.comment = info.comment
                    zout.writestr(new_info, data)
            shutil.move(tmp_name, dst)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--check", action="store_true", help="only report violations")
    args = parser.parse_args(argv)

    if args.check:
        problems = native_lib_violations(args.input)
        if problems:
            for problem in problems:
                print(f"FAIL {problem}")
            return 1
        print("PASS: every lib/**/*.so entry is stored uncompressed")
        return 0

    if not args.output:
        parser.error("output APK is required unless --check is used")

    changed = normalize(args.input, args.output)
    problems = native_lib_violations(args.output)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(f"PASS: normalised {changed} native librar(y/ies) to STORED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
