#!/usr/bin/env python3
"""Regression checks for ALVSIA 6.0.0 release identity and Xop fail-closed behavior."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    p = ROOT / path
    if not p.is_file():
        raise SystemExit(f"FAIL: missing {path}")
    return p.read_text(encoding="utf-8")

gradle = read("app/build.gradle.kts")
codemagic = read("codemagic.yaml")
final_workflow = read(".github/workflows/alvsia-final-release.yml")
readme = read("README.md")

code_match = re.search(r"versionCode\s*=\s*(\d+)", gradle)
name_match = re.search(r'versionName\s*=\s*"([^"]+)"', gradle)
if not code_match or not name_match:
    raise SystemExit("FAIL: Gradle release identity cannot be parsed")
version_code, version_name = code_match.group(1), name_match.group(1)
if (version_code, version_name) != ("100", "6.0.0-smart-premium"):
    raise SystemExit(f"FAIL: unexpected Gradle identity {(version_code, version_name)!r}")

expected_badging = (
    f"package: name='com.alvsia.pro' versionCode='{version_code}' "
    f"versionName='{version_name}'"
)
if expected_badging not in codemagic:
    raise SystemExit("FAIL: CodeMagic APK identity gate differs from Gradle")
if "5.5.2" in codemagic:
    raise SystemExit("FAIL: stale 5.5.2 release labels remain in CodeMagic")

pack_gate = 'if [ "${ALVSIA_XOPPROTECTOR_ENABLED:-true}" != "true" ]; then'
sign_gate = 'if [ "${ALVSIA_XOPPROTECTOR_ENABLED:-true}" = "true" ]; then'
if pack_gate not in codemagic or sign_gate not in codemagic:
    raise SystemExit("FAIL: XopProtector default differs between pack and sign stages")
xop_command = next((line for line in final_workflow.splitlines() if 'java -jar "$PACKER"' in line), "")
if "--encrypt-assets" in xop_command or re.search(r"^\\s*--encrypt-assets(?:\\s|$)", codemagic, re.MULTILINE):
    raise SystemExit("FAIL: Xop asset encryption is unsafe until runtime readers use ProtectorAssets")
if "ignore_failure: true" in codemagic:
    raise SystemExit("FAIL: a CodeMagic step can silently ignore a release failure")
if "ERROR: XopProtector is required for this release" not in codemagic:
    raise SystemExit("FAIL: missing Xop candidate does not fail the release")
if any(flag not in codemagic for flag in ("--profile industry", "--protect-so", "--detect-proxy", "--so-decrypt-mode lazy")):
    raise SystemExit("FAIL: CodeMagic Xop security options are incomplete")
if any(flag not in final_workflow for flag in ("--profile industry", "--protect-so", "--detect-proxy", "--so-decrypt-mode lazy")):
    raise SystemExit("FAIL: GitHub Xop security options are incomplete")
if "--profile industry" not in codemagic or "--protect-so" not in codemagic:
    raise SystemExit("FAIL: expected XopProtector profile/SO protection is not configured")

if "ALVSIA_SMART_PREMIUM_6.0.0-xop-signed.apk" not in final_workflow:
    raise SystemExit("FAIL: GitHub final workflow does not publish the 6.0.0 Xop artifact")
if "python3 tools/prepare_xop_final.py" not in final_workflow:
    raise SystemExit("FAIL: Xop native provenance normalization is missing")
if "6.0.0-smart-premium" not in readme or "Version code | 100" not in readme:
    raise SystemExit("FAIL: README release identity differs from Gradle")

print("RELEASE PIPELINE CONSISTENCY: PASS")
print(f"- Gradle / CodeMagic identity: {version_name} (versionCode {version_code})")
print("- XopProtector default-on and fail-closed behavior: PASS")
print("- GitHub Xop artifact/provenance stage: PASS")
print("- README release identity: PASS")
print("- TLS backup pin and insns_xor_key remain separate evidence-gated audits; this test does not invent values.")
