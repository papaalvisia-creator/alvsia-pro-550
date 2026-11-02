#!/usr/bin/env python3
"""Validate final signed APK packaging, alignment, signature, and app identity."""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

def command(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(result.stdout or "Validation command failed")
    return result.stdout

def main():
    if len(sys.argv) != 5:
        raise SystemExit("usage: validate_apk.py APK APKSIGNER ZIPALIGN AAPT")
    apk, signer, aligner, aapt = map(Path, sys.argv[1:])
    for item in (apk, signer, aligner, aapt):
        if not item.is_file():
            raise SystemExit("Missing APK or Android validation tool: " + str(item))
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("Duplicate ZIP entries detected")
        bad = archive.testzip()
        if bad:
            raise SystemExit("APK ZIP CRC failure: " + bad)
        required = (
            "AndroidManifest.xml", "classes.dex",
            "lib/arm64-v8a/librasp_guard.so",
            "assets/chaquopy/app.imy", "assets/nx/i.dat",
            "lib/arm64-v8a/libprotector.so", "assets/protector/dexes.zip",
        )
        missing = [name for name in required if name not in names]
        if missing:
            raise SystemExit("Required APK entries missing: " + ", ".join(missing))
    alignment = command([str(aligner), "-c", "-v", "4", str(apk)])
    if "Verification successful" not in alignment:
        raise SystemExit("APK alignment verification did not pass")
    signature = command([str(signer), "verify", "--verbose", "--print-certs", str(apk)])
    if "Verified using v2 scheme" not in signature or "Verified using v3 scheme" not in signature:
        raise SystemExit("APK v2/v3 signature verification did not pass")
    identity = command([str(aapt), "dump", "badging", str(apk)])
    expected = "package: name='com.alvsia.pro' versionCode='98' versionName='5.5.2-hardened'"
    if expected not in identity:
        raise SystemExit("APK package or version does not match release")
    print("APK_SHA256=" + hashlib.sha256(apk.read_bytes()).hexdigest())
    print("PASS: ZIP integrity, unique entries, required payloads, alignment, signature and package identity")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
