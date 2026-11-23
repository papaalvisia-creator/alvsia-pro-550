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


def alignment_check_args(aligner: Path, apk: Path) -> list[str]:
    """Require 16 KiB page alignment for every uncompressed native library."""
    return [str(aligner), "-c", "-P", "16", "-v", "4", str(apk)]

def expected_package_identity(config_path: Path = ROOT / "app/build.gradle.kts") -> tuple[str, str, str]:
    """Read package/version identity from the active Gradle release configuration."""
    config = config_path.read_text(encoding="utf-8")
    patterns = (
        r'applicationId\s*=\s*"([^"]+)"',
        r'versionCode\s*=\s*(\d+)',
        r'versionName\s*=\s*"([^"]+)"',
    )
    matches = [re.search(pattern, config) for pattern in patterns]
    if not all(matches):
        raise SystemExit("Gradle applicationId/versionCode/versionName is missing or malformed")
    return tuple(match.group(1) for match in matches)


def package_identity(aapt_output: str) -> tuple[str, str, str]:
    """Extract package/version identity from aapt dump badging output."""
    package_line = next((line for line in aapt_output.splitlines() if line.startswith("package: ")), "")
    match = re.search(
        r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",
        package_line,
    )
    if not match:
        raise SystemExit("aapt could not read APK package/version metadata: " + package_line)
    return match.groups()

def validate_required_entries(names: set[str], read_entry) -> None:
    """Accept either plaintext sealed index or Xop PAS1-encrypted index."""
    required = {
        "AndroidManifest.xml", "classes.dex",
        "lib/arm64-v8a/librasp_guard.so",
        "assets/chaquopy/app.imy",
        "lib/arm64-v8a/libprotector.so", "assets/protector/dexes.zip",
    }
    missing = sorted(required - names)
    if missing:
        raise SystemExit("Required APK entries missing: " + ", ".join(missing))

    plain_index = "assets/nx/i.dat"
    encrypted_index = "assets/protector/aenc/nx/i.dat"
    if plain_index not in names and encrypted_index not in names:
        raise SystemExit("Required sealed JAR index missing (plaintext or Xop PAS1)")
    if encrypted_index in names:
        if "assets/protector/assets.map" not in names:
            raise SystemExit("Xop encrypted asset map missing")
        if not read_entry(encrypted_index).startswith(b"PAS1"):
            raise SystemExit("Xop sealed JAR index has an invalid PAS1 header")


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
        validate_required_entries(set(names), archive.read)
    alignment = command(alignment_check_args(aligner, apk))
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
    identity_output = command([str(aapt), "dump", "badging", str(apk)])
    expected = expected_package_identity()
    actual = package_identity(identity_output)
    if actual != expected:
        raise SystemExit(f"APK package/version mismatch; expected={expected!r}, actual={actual!r}")
    print("APK_SHA256=" + hashlib.sha256(apk.read_bytes()).hexdigest())
    print("PASS: ZIP integrity, unique entries, required payloads, alignment, v2/v3 signature, certificate pin and package identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
