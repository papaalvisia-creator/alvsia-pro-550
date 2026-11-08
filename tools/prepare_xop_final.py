#!/usr/bin/env python3
"""Normalize XOP output while preserving verifiable native-engine provenance."""
from __future__ import annotations
import hashlib
import io
import sys
import zipfile
from pathlib import Path

PAIRS = (
    ("assets/engine_licenses/unluac-rs-android-arm64.sha256",
     "assets/engine_licenses/unluac-rs-android-arm64.manifest",
     "lib/arm64-v8a/libunluac-cli.so"),
    ("assets/engine_licenses/luau-decompiler-android-arm64.sha256",
     "assets/engine_licenses/luau-decompiler-android-arm64.manifest",
     "lib/arm64-v8a/libluau-decompiler-cli.so"),
)
FORBIDDEN_BASENAMES = {"rebrand_config.txt", "app-metadata.properties"}
VCS_SUFFIX = "version-control-info.textproto"

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_zip(path: Path) -> tuple[zipfile.ZipFile, io.BytesIO]:
    raw = path.read_bytes()
    return zipfile.ZipFile(io.BytesIO(raw), "r"), io.BytesIO()

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: prepare_xop_final.py <signed-baseline.apk> <xop-candidate.apk>")
    baseline_path, candidate_path = map(Path, sys.argv[1:])
    with zipfile.ZipFile(baseline_path) as baseline, zipfile.ZipFile(candidate_path) as candidate:
        baseline_names = set(baseline.namelist())
        candidate_names = set(candidate.namelist())
        replacements: dict[str, bytes] = {}
        for checksum_name, manifest_name, binary_name in PAIRS:
            if not {checksum_name, manifest_name, binary_name} <= baseline_names:
                raise SystemExit(f"baseline missing native provenance entries for {binary_name}")
            original_parts = baseline.read(checksum_name).decode("ascii").split()
            original_hash = original_parts[0] if original_parts else ""
            actual_original = digest(baseline.read(binary_name))
            if len(original_hash) != 64 or original_hash != actual_original:
                raise SystemExit(f"baseline native checksum mismatch: {binary_name}")
            if not {checksum_name, manifest_name, binary_name} <= candidate_names:
                raise SystemExit(f"XOP candidate missing native provenance entries for {binary_name}")
            protected_hash = digest(candidate.read(binary_name))
            checksum_text = f"{protected_hash}  {binary_name.split('/')[-1]}\\n"
            manifest = candidate.read(manifest_name).decode("utf-8")
            manifest = manifest.rstrip() + (
                f"\\nsource_sha256={original_hash}"
                f"\\nxop_protected_sha256={protected_hash}\\n"
            )
            replacements[checksum_name] = checksum_text.encode("ascii")
            replacements[manifest_name] = manifest.encode("utf-8")

        output = io.BytesIO()
        removed = []
        with zipfile.ZipFile(output, "w") as target:
            for info in candidate.infolist():
                basename = Path(info.filename).name.lower()
                if basename in FORBIDDEN_BASENAMES or info.filename.endswith(VCS_SUFFIX):
                    removed.append(info.filename)
                    continue
                payload = replacements.get(info.filename, candidate.read(info.filename))
                target.writestr(info, payload)
        candidate_path.write_bytes(output.getvalue())
        print("XOP_FINAL_NORMALIZATION=PASS")
        print("NATIVE_PROVENANCE=PASS (baseline hashes verified; protected hashes recorded)")
        print("REMOVED_METADATA=" + (", ".join(removed) if removed else "none"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
