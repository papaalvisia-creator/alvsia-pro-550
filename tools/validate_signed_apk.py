#!/usr/bin/env python3
"""Verify a signed ALVSIA PRO APK with Android SDK tools and archive checks.

Usage: validate_signed_apk.py APK APKSIGNER ZIPALIGN AAPT
The validator checks the artifact itself; it does not sign or modify the APK.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path


EXPECTED_PACKAGE = "com.alvsia.pro"
EXPECTED_VERSION_CODE = "98"
EXPECTED_VERSION_NAME = "5.5.2-hardened"


def run_tool(argv: list[str]) -> str:
    result = subprocess.run(
        argv, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(
            "command failed (exit %d): %s\n%s"
            % (result.returncode, " ".join(argv), result.stdout[-5000:])
        )
    return result.stdout


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "usage: validate_signed_apk.py APK APKSIGNER ZIPALIGN AAPT",
            file=sys.stderr,
        )
        return 2

    apk, apksigner, zipalign, aapt = map(Path, sys.argv[1:])
    for label, path in (
        ("APK", apk), ("apksigner", apksigner),
        ("zipalign", zipalign), ("aapt", aapt),
    ):
        if not path.is_file():
            print("FAIL %s not found: %s" % (label, path), file=sys.stderr)
            return 2
    if apk.stat().st_size == 0:
        print("FAIL APK is empty", file=sys.stderr)
        return 1

    checks = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        checks.append((label, bool(ok), detail))

    try:
        with zipfile.ZipFile(apk, "r") as archive:
            bad_member = archive.testzip()
            check("APK ZIP integrity", bad_member is None, bad_member or "")
            names = set(archive.namelist())
            check("AndroidManifest.xml present", "AndroidManifest.xml" in names)
            check(
                "classes.dex present",
                any(re.fullmatch(r"classes([0-9]+)?[.]dex", name) for name in names),
            )
            check(
                "arm64 native payload present",
                any(name.startswith("lib/arm64-v8a/") and name.endswith(".so") for name in names),
            )
    except (OSError, zipfile.BadZipFile) as exc:
        print("FAIL cannot read APK ZIP: %s" % exc, file=sys.stderr)
        return 1

    try:
        aligned = run_tool([str(zipalign), "-c", "-v", "4", str(apk)])
        check("4-byte ZIP alignment", True, aligned.strip().splitlines()[-1:] or [""])
    except Exception as exc:
        check("4-byte ZIP alignment", False, str(exc))

    try:
        signature = run_tool([
            str(apksigner), "verify", "--verbose", "--print-certs", str(apk)
        ])
        v2 = re.search(
            r"Verified using v2 scheme .*: *true",
            signature, re.I,
        )
        v3 = re.search(
            r"Verified using v3 scheme .*: *true",
            signature, re.I,
        )
        check("APK Signature Scheme v2", bool(v2), "v2 signature must verify")
        check("APK Signature Scheme v3", bool(v3), "v3 signature must verify")
        cert = re.search(r"certificate SHA-256 digest: ([0-9a-f:]+)", signature, re.I)
        check("signing certificate digest reported", bool(cert))
        if cert:
            print("CERT_SHA256=" + cert.group(1).replace(":", "").lower())
    except Exception as exc:
        check("APK signature verification", False, str(exc))

    try:
        badging = run_tool([str(aapt), "dump", "badging", str(apk)])
        package = re.search(
            r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'",
            badging, re.M,
        )
        check("APK package metadata parsed", bool(package))
        if package:
            check("package ID", package.group(1) == EXPECTED_PACKAGE, package.group(1))
            check("version code", package.group(2) == EXPECTED_VERSION_CODE, package.group(2))
            check("version name", package.group(3) == EXPECTED_VERSION_NAME, package.group(3))
    except Exception as exc:
        check("aapt badging", False, str(exc))

    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    print("APK=" + str(apk))
    print("SIZE=" + str(apk.stat().st_size))
    print("SHA256=" + digest)
    for label, ok, detail in checks:
        print(("PASS " if ok else "FAIL ") + label + ((": " + detail) if detail else ""))

    failures = [label for label, ok, _ in checks if not ok]
    if failures:
        print("RESULT=FAIL (%d checks)" % len(failures))
        return 1
    print("RESULT=PASS (%d checks)" % len(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
