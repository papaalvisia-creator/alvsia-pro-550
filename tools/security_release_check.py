#!/usr/bin/env python3
"""Source-level release gates for the ALVISIA PRO main-only sealed release pipeline."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "app/src/main/python"
JAVA = ROOT / "app/src/main/java/com/alvsia/pro"
fail = []

def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        fail.append(f"missing/unreadable: {path.relative_to(ROOT)}")
        return ""

gradle = read(ROOT / "app/build.gradle.kts")
manifest = read(ROOT / "app/src/main/AndroidManifest.xml")
panel = read(JAVA / "panel/PanelClient.kt")
vault = read(JAVA / "panel/Vault.kt")
session = read(JAVA / "sec/SessionGate.kt")
native = read(ROOT / "app/src/main/cpp/rasp_guard.cpp")
native_guard = read(JAVA / "sec/NativeGuard.kt")
dex_guardian = read(JAVA / "sec/DexGuardian.kt")
rasp_engine = read(JAVA / "sec/RaspEngine.kt")
tool_engine = read(JAVA / "tool/ToolEngine.kt")
bridge = read(PY / "alvsia_bridge.py")
loader = read(PY / "sealed_loader.py")
python_panel = read(PY / "pinned_http.py")
seal_script = read(ROOT / "tools/seal_python.py")
audit_script = read(ROOT / "tools/audit_release_apk.py")
codemagic = read(ROOT / "codemagic.yaml")
workflow = read(ROOT / ".github/workflows/android-validation.yml")
profile = read(ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt")

required_modules = {
    "alvsia_bridge_impl.py", "alvsia_metadata.py", "alvsia_private.py", "alvsia_vm_protect.py", "lua_engine/pattern_registry.py",
    "alvsia_core.py", "alvsia_ultimate.py",
    "alvsia_ultimate_compat.py", "alvsia_features.py", "sm4_secret_registry.py", "sm4_material.py", "pinned_http.py",
    "lua_engine/lua_decompiler_final.py", "lua_engine/lua_protector.py",
    "lua_engine/t24.py",
    "lua_output_validator.py", "lua_string_recover.py",
    "lua_engine/engine.py", "lua_engine/decompiler53.py", "lua_engine/bgmi.py",
    "lua_engine/luajit_decompiler.py", "lua_engine/container.py",
    "lua_engine/detector.py", "lua_engine/multi_format.py",
    "lua_engine/streaming_decompiler.py", "lua_engine/orchestrator.py", "lua_engine/protection.py", "lua_engine/protection_pipeline.py", "lua_engine/vm_deobfuscator.py",
}
script_modules = set(re.findall(r'"([^"]+\.py)"', seal_script.split("MODULES = (",1)[-1].split(")",1)[0]))
loader_modules = set(re.findall(r'"([^"]+)":', loader.split("_MAP = {", 1)[-1].split("}", 1)[0]))
if required_modules - script_modules:
    fail.append("Python seal script misses modules: " + ", ".join(sorted(required_modules - script_modules)))
expected_loader = {p[:-3].replace("/", ".") for p in required_modules}
if expected_loader - loader_modules:
    fail.append("sealed loader map misses modules: " + ", ".join(sorted(expected_loader - loader_modules)))
if script_modules - required_modules:
    fail.append("seal script contains unreviewed modules: " + ", ".join(sorted(script_modules - required_modules)))
if loader_modules != expected_loader:
    fail.append("sealed loader inventory differs from required module inventory: missing=" +
                ", ".join(sorted(expected_loader - loader_modules)) + "; unexpected=" +
                ", ".join(sorted(loader_modules - expected_loader)))
if script_modules != required_modules:
    fail.append("seal script inventory differs from required module inventory")
for rel in required_modules:
    if not (PY / rel).is_file():
        fail.append("protected source missing from developer/test tree: " + rel)
if "sealed_loader.install()" not in bridge or "ALVSIA_SEALED_RUNTIME" not in bridge:
    fail.append("bridge bootstrap does not install the sealed loader conditionally")
if "def run_tool(" in bridge and "import alvsia_bridge_impl as impl" not in bridge:
    fail.append("plaintext bridge must delegate tool routing to the sealed implementation")
if len(bridge.encode("utf-8")) >= 2000 or "if mid == 1" in bridge:
    fail.append("plaintext bridge must remain a small stub without module-routing logic")
if "isTokenCurrent(token)" not in bridge:
    fail.append("bridge must compare the supplied token with the authoritative Kotlin session")
if "SessionGate.isSessionAuthorized()" not in loader:
    fail.append("sealed imports must check the live Kotlin session gate")
if "SessionGate.isSessionAuthorized()" not in read(PY / "alvsia_bridge_impl.py"):
    fail.append("sealed tool dispatch must check the live Kotlin session gate")
if "ALVSIA_SEAL_SEED" in tool_engine or "ALVSIA_SEAL_SEED" in loader:
    fail.append("seal seed must never be exposed through Python process environment")
if "sealBuildId()" not in loader or "_BUILD_ID" in loader or "_CERT_SHA256" in loader:
    fail.append("sealed loader must obtain its build ID natively and keep certificate digest out of Python")
if "fun sealBuildId(): String?" not in native_guard or "nativeSealBuildId" not in native:
    fail.append("sealed build ID must be provided through the native bridge")
if "fun decryptSealedPayload(payload: ByteArray, buildId: String)" not in native_guard or "nativeSealSeed()" not in native_guard:
    fail.append("Kotlin/native bridge must decrypt sealed payload without exposing the seed to Python")
if "ALVSIA_SEALED_RUNTIME" not in tool_engine:
    fail.append("ToolEngine does not enable sealed runtime after session validation")
if "nativeSealSeed" not in native_guard or "nativeSealSeed" not in native:
    fail.append("native seal seed JNI is not wired end-to-end")
if "AES/GCM/NoPadding" not in native_guard or "cipher.updateAAD(magic)" not in native_guard:
    fail.append("Kotlin/native bridge lacks authenticated AES-GCM decryption")
if "ALVSEAL2" not in seal_script or "AESGCM" not in seal_script:
    fail.append("Python sealing script is missing authenticated encryption")
if "inspectXopPayload(ctx)" not in dex_guardian or '"assets/protector/dexes.zip"' not in dex_guardian:
    fail.append("DexGuardian does not recognize and validate the XopProtector payload")
if "0x50, 0x44, 0x58, 0x31" not in dex_guardian or "xop_payload_invalid" not in dex_guardian:
    fail.append("DexGuardian Xop path is missing encrypted-container integrity checks")
if "tools/seal_python.py --seal" not in codemagic or "tools/seal_python.py --restore" not in codemagic:
    fail.append("CodeMagic does not seal and restore protected Python modules")
if "tools/audit_release_apk.py" not in codemagic or "tools/audit_release_apk.py" not in workflow:
    fail.append("actual APK audit is not wired into both release pipelines")
if 'python3 tools/audit_release_apk.py "$SIGNED_APK"' not in codemagic:
    fail.append("CodeMagic must audit the exact final signed APK selected for signing after signing")
release_code = re.search(r"versionCode\s*=\s*(\d+)", gradle)
release_name = re.search(r'versionName\s*=\s*"([^"]+)"', gradle)
expected_release_identity = (
    f"versionCode='{release_code.group(1)}' versionName='{release_name.group(1)}'"
    if release_code and release_name else ""
)
if ('aapt" dump badging "$SIGNED_APK"' not in codemagic
        or not expected_release_identity
        or expected_release_identity not in codemagic):
    fail.append("CodeMagic must verify final APK package, versionCode, and versionName against Gradle")
if 'zipalign" -c -v 4 "$SIGNED_APK"' not in codemagic or 'sha256sum "$SIGNED_APK"' not in codemagic:
    fail.append("CodeMagic must verify final APK alignment and emit its SHA-256 fingerprint")
if "BuildConfig.VERSION_NAME" not in profile:
    fail.append("profile version label must use the actual built APK version")
if "rebrand_config.txt" not in audit_script or "app-metadata.properties" not in audit_script:
    fail.append("APK audit must reject packaged local rebrand/build metadata")
if "forbidden_inner" not in audit_script or "forbidden_package_names" not in audit_script:
    fail.append("APK audit must inspect nested Chaquopy app.imy metadata")
if "vm_extract_payload" not in audit_script or "Feistel-like" not in audit_script:
    fail.append("APK audit must scan plaintext code for exposed protection implementation markers")
if "CM_BRANCH" not in codemagic or '!= "main"' not in codemagic:
    fail.append("CodeMagic release branch is not restricted to main")
if "isMinifyEnabled = true" not in gradle or "isShrinkResources = true" not in gradle:
    fail.append("release R8/minification/resource shrinking is disabled")
if "-keepattributes SourceFile,LineNumberTable" in read(ROOT / "app/proguard-rules.pro"):
    fail.append("release ProGuard explicitly preserves source/line debug metadata")
if "-g0" not in read(ROOT / "app/src/main/cpp/CMakeLists.txt"):
    fail.append("native release build does not explicitly disable debug info")
if 'implementation("com.securevale:rasp-android:0.7.1")' in gradle:
    fail.append("recognizable SecureVale Android RASP SDK dependency remains")
if "SecureAppChecker" in rasp_engine or "com.securevale." in rasp_engine:
    fail.append("RaspEngine still references removed SecureVale SDK classes")
dual_vm = read(JAVA / "sec/DualVmGuard.kt")
if "DualVmGuard.inspect(ctx)" not in rasp_engine:
    fail.append("RaspEngine does not execute the dual-layer runtime integrity gate")
if "OP_PACKAGE" not in dual_vm or "OP_NATIVE" not in dual_vm or "dlrg_vm_bounds" not in dual_vm:
    fail.append("dual-layer runtime gate is missing bounded VM opcodes or native-stage checks")
if "NativeGuard.scanFlags()" not in dual_vm or "NativeGuard.dualVmNativeFlags()" not in dual_vm:
    fail.append("dual-layer runtime gate does not cross-check the native VM and native RASP scanner")
if "native_vm_flags" not in native or '"nativeVmFlags"' not in native or "fun dualVmNativeFlags()" not in native_guard:
    fail.append("native mini-VM JNI entry point is not wired end-to-end")
for opcode in ("case 0x11:", "case 0x22:", "case 0x33:", "case 0x44:", "case 0x55:", "case 0x66:"):
    if opcode not in native:
        fail.append("native mini-VM is missing bounded integrity opcode " + opcode)
if 'SEED_ENV = "ALVSIA_SEAL_SEED_HEX"' not in seal_script:
    fail.append("Python sealing does not use the per-build seed environment variable")
if "secrets.token_hex(32)" not in workflow or "secrets.token_hex(32)" not in codemagic:
    fail.append("CI/CodeMagic do not generate a fresh per-build seal seed")
if "00112233445566778899aabbccddeeff" in native or "00112233445566778899aabbccddeeff" in seal_script:
    fail.append("fixed public seal seed remains in source")
if "META-INF/version-control-info.textproto" not in gradle or '"**/version-control-info.textproto"' not in gradle:
    fail.append("VCS metadata is not excluded from release packaging")
if "android.permission.DUMP" in manifest:
    fail.append("unnecessary android.permission.DUMP remains in manifest")
if "android.permission.DELETE_PACKAGES" in manifest or "android.permission.CHANGE_NETWORK_STATE" in manifest:
    fail.append("unused package-delete/network-state permissions remain in manifest")
if ".certificatePinner(Vault.certPinner())" not in panel or "clientPinned.newCall(req).execute()" not in panel:
    fail.append("PanelClient TLS policy is not wired")
if 'sha256/84+S6cn1vo+IjlQMR5mvqIe5XKMPh28WV9xYVtFKTkk=' not in vault or '.add("alvsiapanel.unaux.com", "sha256/' not in vault:
    fail.append("measured Unaux SPKI pin is missing from the active OkHttp certificate pinner")
network_config = read(ROOT / "app/src/main/res/xml/network_security_config.xml")
if ("networkSecurityConfig" not in manifest
        or "alvsiapanel.unaux.com" not in network_config
        or "<pin-set>" not in network_config
        or "84+S6cn1vo+IjlQMR5mvqIe5XKMPh28WV9xYVtFKTkk=" not in network_config
        or "alvsiapanel.unaux.com" not in vault):
    fail.append("new-panel network security configuration or measured SPKI pin is missing")
if ("alvsiapanel.unaux.com" not in python_panel
        or "84+S6cn1vo+IjlQMR5mvqIe5XKMPh28WV9xYVtFKTkk=" not in python_panel
        or "alvsiapro.cc.cd" in python_panel
        or "api.alvsiapro.cc.cd" in python_panel):
    fail.append("Python HTTP pinning must use only the active Unaux panel host and measured SPKI pin")
if "KEY_ALGORITHM_HMAC_SHA256" not in session or "age in 0..SESSION_TTL" not in session:
    fail.append("SessionGate HMAC or future/expiry timestamp checks are missing")
if ("if (runtimeHostile(ctx))" not in session
        or "native_rasp_unavailable" not in session
        or 'throw SecurityException("BLOCKED:runtime_hostile")' not in session):
    fail.append("SessionGate must recheck live hooks each dispatch and fail closed if release JNI RASP is unavailable")
if "DualVmGuard.inspect(ctx)" not in session:
    fail.append("SessionGate must re-run the dual-layer runtime gate at each protected dispatch")
if "fun isNativeLoaded(): Boolean = nativeLoaded" not in native_guard:
    fail.append("NativeGuard load-state API is missing; release cannot detect JNI downgrade")
guard = read(JAVA / "sec/Guard.kt")
if ("fun runtimeHostile(ctx: Context)" not in guard
        or "private val HARD_RUNTIME_MARKERS" not in guard
        or "private val SOFT_HOOK_MARKERS" not in guard):
    fail.append("Guard must distinguish hard active-instrumentation signals from soft hook-library signals")
ultimate = read(PY / "alvsia_ultimate.py")
if "alvsiapro.cc.cd" in ultimate or "api.alvsiapro.cc.cd" in ultimate:
    fail.append("bundled ultimate engine still references the retired panel host")
if 'def check_password_login()' in ultimate and 'SessionGate.isSessionAuthorized()' not in ultimate:
    fail.append("bundled ultimate engine must defer authentication to the trusted Kotlin session gate")
if "/SKIN_TOOL/main/SKIN_TOOL.zip" in ultimate or "/BGMI_CSV/main/" in ultimate:
    fail.append("external SKIN_TOOL/BGMI_CSV downloads are not commit-pinned")
if "_verify_pinned_git_blob" not in ultimate or "cbd3d0e257963b54f34a908b6864040c7f96fbb1" not in ultimate:
    fail.append("external data download integrity verification is missing")

# Unaux operation-grant contract must match the active panel, and every tool dispatch must fail closed.
operation_grants = read(JAVA / "tool/OperationGrants.kt")
grant_panel = read(JAVA / "panel/PanelClient.kt")
grant_runner = read(JAVA / "tool/PythonBridgeRunner.kt")
grant_core = read(PY / "alvsia_core.py")
grant_ultimate = read(PY / "alvsia_ultimate.py")
grant_bridge_impl = read(PY / "alvsia_bridge_impl.py")
grant_endpoint = read(ROOT / "panel-migration/api/operation_grant.php")
if ("ALVSIA-UNaux-20261028-RSA1" not in operation_grants
        or "alvsia-unaux-rsa1" not in grant_core
        or "alvsia-unaux-rsa1" not in grant_ultimate
        or "grant_token" not in grant_panel
        or 'response.optString("status") != "ok"' not in grant_panel):
    fail.append("APK and Unaux operation-grant KID/build/response contract is not aligned")
if ("operationFor(moduleId, subId)" not in grant_runner
        or "?: return false to listOf" not in grant_runner
        or "Unaux RSA operation grant unavailable" not in grant_runner):
    fail.append("all Android tool dispatches must request a grant and fail closed on missing mappings or grants")
if ("_alvsia_install_operation_grant_token" not in grant_core
        or "_alv_install_operation_grant_token" not in grant_ultimate
        or "claims.get('session_hash') != session" not in grant_core
        or "claims.get('hwid_hash')" not in grant_core
        or "expires-issued > 180" not in grant_core
        or "ALVSIA_CORE_RSA_N_B64U" not in grant_core):
    fail.append("Python core JWT verifier is missing signature/session/device/TTL checks")
if ("core._alvsia_require_operation((grant_operation,))" not in grant_bridge_impl
        or "module/subtool has no Unaux grant mapping" not in grant_bridge_impl):
    fail.append("Python dispatch must enforce the signed module grant before tool execution")
if ("ALVSIA_GRANT_KID='alvsia-unaux-rsa1'" not in grant_endpoint
        or "ALVSIA_GRANT_BUILD_ID='ALVSIA-UNaux-20261028-RSA1'" not in grant_endpoint
        or "openssl_sign($input,$sig,$privateKey,OPENSSL_ALGO_SHA256)" not in grant_endpoint
        or "grant_rate_limit('operation_grant',30,60)" not in grant_endpoint
        or "ALVSIA_GRANT_TTL=180" not in grant_endpoint
        or "grant_signing_key_mismatch" not in grant_endpoint
        or "ALVSIA_GRANT_PUBLIC_N_B64URL" not in grant_endpoint):
    fail.append("Unaux endpoint must sign the aligned JWT contract, rate-limit, and enforce 180-second TTL")

# ---------------------------------------------------------------------------
# Embedded-secret scan across EVERY Python module (not just the registry).
# This is AST-based so it does not trip on comments or the scanner's own rules.
# ---------------------------------------------------------------------------
import ast

# Known historical SM4 material that must never reappear in the source tree.
# No plaintext historical key values are stored in this scanner.
SECRET_NAME_PREFIXES = ("SM4_SECRET", "SM4_KEY", "SM4_CANDIDATE")
SECRET_NAME_EXCLUDE_SUFFIXES = (
    "_VERSION", "_EXPECTED_COUNT", "_COUNT", "_SET", "_LEN", "_NAME",
    "_PATTERN", "_LABEL", "_TYPE", "_KIND",
)


def _is_secret_name(name: str) -> bool:
    if not name.startswith(SECRET_NAME_PREFIXES):
        return False
    if name.endswith(SECRET_NAME_EXCLUDE_SUFFIXES):
        return False
    return True


def _looks_like_key_literal(value: str) -> bool:
    """Heuristic for a 16..64 char opaque key-ish string literal."""
    if not isinstance(value, str) or not (16 <= len(value) <= 64):
        return False
    if any(ch.isspace() for ch in value):
        return False
    # Reject obvious human text / paths / identifiers with spaces or dots.
    return True


def _looks_like_historical_sm4_candidate(value: str) -> bool:
    """Detect the three known SM4 candidate families without storing their values."""
    if not isinstance(value, str) or len(value) != 20:
        return False
    # SM4_SECRET_NEW: lower/upper/digit repeating, with a 2-char tail.
    if all(
        ch.islower() if i % 3 == 0 else ch.isupper() if i % 3 == 1 else ch.isdigit()
        for i, ch in enumerate(value)
    ):
        return True
    # SM4_SECRET_4: lowercase + digits only, digit-heavy.
    if (value.isalnum()
            and sum(ch.isdigit() for ch in value) >= 10
            and sum(ch.islower() for ch in value) >= 5
            and not any(ch.isupper() for ch in value)):
        return True
    # SM4_SECRET_2: punctuation marker plus mixed alphanumeric composition.
    if (any(ch in "$*" for ch in value)
            and sum(ch.isupper() for ch in value) >= 5
            and sum(ch.islower() for ch in value) >= 3
            and any(ch.isdigit() for ch in value)):
        return True
    return False


def _artifact_hygiene_violations(root: Path, tracked_files=None) -> list[str]:
    """Reject compiled caches and local signing material in source exports.

    In a Git checkout, inspect only tracked paths so normal test-created
    __pycache__ files do not make CI flaky. In an exported source directory
    without .git, inspect every file: an archive containing .pyc/cache data is
    not a clean source deliverable.
    """
    if tracked_files is None:
        git_dir = root / ".git"
        if git_dir.exists():
            result = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z"],
                capture_output=True, check=False,
            )
            if result.returncode == 0:
                tracked_files = [
                    root / Path(item.decode("utf-8", "replace"))
                    for item in result.stdout.split(b"\x00") if item
                ]
        if tracked_files is None:
            tracked_files = [p for p in root.rglob("*") if p.is_file()]

    violations = []
    for path in tracked_files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        parts = set(rel.parts)
        name = path.name.lower()
        if path.suffix.lower() == ".pyc" or "__pycache__" in parts:
            violations.append(f"compiled Python cache in source deliverable: {rel}")
        if ".pytest_cache" in parts:
            violations.append(f"pytest cache in source deliverable: {rel}")
        if name == ".env" or name.startswith(".env.") and name != ".env.example":
            violations.append(f"local environment secret file in source deliverable: {rel}")
        if path.suffix.lower() in {".jks", ".keystore", ".p12", ".pfx", ".key"}:
            violations.append(f"local signing/private-key material in source deliverable: {rel}")
    return violations


for py_file in sorted(PY.rglob("*.py")):
    rel = py_file.relative_to(ROOT)
    try:
        src = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        fail.append(f"unreadable python module: {rel}")
        continue
    try:
        tree = ast.parse(src, filename=str(rel))
    except SyntaxError as exc:
        fail.append(f"python module does not parse ({rel}): {exc}")
        continue
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _looks_like_historical_sm4_candidate(node.value)):
            fail.append(f"historical SM4 candidate-shaped literal found in {rel}")
            continue
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None:
            continue
        names = []
        for t in targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
            elif isinstance(t, ast.Attribute):
                names.append(t.attr)
        if not any(_is_secret_name(n) for n in names):
            continue
        # Only flag literal string/bytes constants (not calls like os.environ.get).
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            if _looks_like_key_literal(value.value):
                fail.append(
                    f"hardcoded secret literal assigned to {names[0]} in {rel}"
                )
        elif isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    if _looks_like_key_literal(elt.value):
                        fail.append(
                            f"hardcoded secret literal in {names[0]} collection in {rel}"
                        )
                        break

# A clean source export must not carry generated bytecode/cache or local
# signing material. Git checkouts inspect tracked paths only; ZIP/RAR exports
# without .git are scanned in full.
fail.extend(_artifact_hygiene_violations(ROOT))

# Python source is scanned by AST above; release APK contents are
# independently inspected by tools/audit_release_apk.py.
if fail:
    print("SECURITY SOURCE CHECK: FAIL")
    print("\n".join("- " + x for x in fail))
    sys.exit(1)
print("SECURITY SOURCE CHECK: PASS")
print(f"- protected Python modules scheduled for sealing: {len(required_modules)}")
print("- AES-GCM decryption in Kotlin/native bridge; seed and cert digest not exposed to Python")
print("- New-panel TLS CA/hostname validation, SessionGate HMAC/TTL, R8, VCS stripping checked")
print("- CodeMagic release restricted to main; APK audit required")
print("NOTE: one Termux-measured Unaux SPKI pin is enforced; no verified backup pin was supplied, so certificate rotation must be re-measured. Native seed is build-bound obfuscation, not a server secret.")
