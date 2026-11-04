#!/usr/bin/env python3
"""Validate final signed APK packaging, alignment, signature, app identity and certificate pin."""
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(result.stdout or "Validation command failed")
    return result.stdout


def expected_certificate_sha256(config_path: Path = ROOT / "app/build.gradle.kts") -> str:
    """Read the release certificate pin from the same config used by the app."""
    config = config_path.read_text(encoding="utf-8")
    match = re.search(r'CERT_SHA256.*?([0-9a-fA-F]{64})', config)
    if not match:
        raise SystemExit("Release CERT_SHA256 pin is missing or malformed")
    return match.group(1).lower()


def certificate_sha256(signature_output: str) -> str:
    """Extract and normalize apksigner's certificate SHA-256 fingerprint."""
    match = re.search(r'certificate SHA-256 digest:\s*([0-9a-fA-F:]+)', signature_output, re.IGNORECASE)
    if not match:
        raise SystemExit("apksigner did not report a certificate SHA-256 digest")
    digest = re.sub(r'[^0-9a-f]', '', match.group(1).lower())
    if len(digest) != 64:
        raise SystemExit("apksigner returned a malformed certificate SHA-256 digest")
    return digest


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
    actual_cert = certificate_sha256(signature)
    expected_cert = expected_certificate_sha256()
    if actual_cert != expected_cert:
        raise SystemExit(
            "APK signing certificate does not match release CERT_SHA256 pin "
            f"(expected {expected_cert}, got {actual_cert})"
        )
    identity = command([str(aapt), "dump", "badging", str(apk)])
    expected = "package: name='com.alvsia.pro' versionCode='98' versionName='5.5.2-hardened'"
    if expected not in identity:
        raise SystemExit("APK package or version does not match release")
    print("APK_SHA256=" + hashlib.sha256(apk.read_bytes()).hexdigest())
    print("PASS: ZIP integrity, unique entries, required payloads, alignment, v2/v3 signature, certificate pin and package identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
