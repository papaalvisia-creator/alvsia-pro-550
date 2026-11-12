#!/usr/bin/env python3
"""Audit the actual ALVISIA release APK for sealed Python/JAR payloads and metadata."""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

EXPECTED_SEALED = {
    "alvsia_bridge_impl.alv",
    "alvsia_metadata.alv",
    "alvsia_private.alv",
    "alvsia_vm_protect.alv",
    "lua_engine_pattern_registry.alv",
    "alvsia_core.alv",
    "alvsia_ultimate.alv",
    "alvsia_ultimate_compat.alv",
    "alvsia_features.alv",
    "sm4_secret_registry.alv",
    "pinned_http.alv",
    "lua_engine_lua_decompiler_final.alv",
    "lua_engine_lua_protector.alv",
    "lua_output_validator.alv",
    "lua_string_recover.alv",
    "lua_engine_engine.alv",
    "lua_engine_decompiler53.alv",
    "lua_engine_bgmi.alv",
    "lua_engine_t24.alv",
    "lua_engine_luajit_decompiler.alv",
    "lua_engine_container.alv",
    "lua_engine_detector.alv",
    "lua_engine_multi_format.alv",
    "lua_engine_streaming_decompiler.alv",
    "lua_engine_orchestrator.alv",
    "lua_engine_protection.alv",
    "lua_engine_protection_pipeline.alv",
    "lua_engine_vm_deobfuscator.alv",
}
PROTECTED_MODULES = {
    "alvsia_bridge_impl", "alvsia_metadata", "alvsia_private", "alvsia_vm_protect", "alvsia_core", "alvsia_ultimate", "alvsia_ultimate_compat",
    "alvsia_features", "sm4_secret_registry", "pinned_http", "lua_engine/lua_decompiler_final",
    "lua_engine/lua_protector", "lua_engine/pattern_registry",
    "lua_output_validator", "lua_string_recover",
    "lua_engine/engine", "lua_engine/decompiler53", "lua_engine/bgmi", "lua_engine/t24",
    "lua_engine/luajit_decompiler", "lua_engine/container", "lua_engine/detector",
    "lua_engine/multi_format", "lua_engine/streaming_decompiler", "lua_engine/orchestrator", "lua_engine/vm_deobfuscator",
}
SEAL_MAGIC = b"ALVSEAL2"
ASSET_MAGIC = b"ALVSA1\x00"
REQUIRE_XOP_PROVENANCE = os.environ.get("ALVSIA_REQUIRE_XOP_PROVENANCE", "1") != "0"

def _axml_strings(data: bytes) -> list[str]:
    """Read Android binary XML string-pool entries without relying on raw string-pool hits."""
    import struct
    pos = 8
    while pos + 8 <= len(data):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, pos)
        if chunk_size < header_size or pos + chunk_size > len(data):
            return []
        if chunk_type == 0x0001 and header_size >= 28:  # RES_STRING_POOL_TYPE
            string_count, style_count, flags, strings_start, _styles_start = struct.unpack_from("<IIIII", data, pos + 8)
            if string_count > 200000 or pos + header_size + string_count * 4 > pos + chunk_size:
                return []
            offsets = struct.unpack_from("<" + "I" * string_count, data, pos + header_size) if string_count else ()
            utf8 = bool(flags & 0x100)
            base = pos + strings_start
            result = []
            for off in offsets:
                p = base + off
                try:
                    if utf8:
                        def read_len(q):
                            n = data[q]
                            if n & 0x80:
                                return ((n & 0x7f) << 8) | data[q + 1], q + 2
                            return n, q + 1
                        _u16len, p = read_len(p)
                        n, p = read_len(p)
                        result.append(data[p:p+n].decode("utf-8", "replace"))
                    else:
                        n = data[p]
                        p += 1
                        if n & 0x80:
                            n = ((n & 0x7f) << 8) | data[p]
                            p += 1
                        result.append(data[p:p + n * 2].decode("utf-16le", "replace"))
                except (IndexError, UnicodeError):
                    result.append("")
            return result
        pos += chunk_size
    return []


def _manifest_declares_permission(data: bytes, permission: str) -> bool:
    """Check actual uses-permission XML nodes, not orphaned strings in a binary XML pool."""
    import struct
    strings = _axml_strings(data)
    if not strings:
        # Fail closed if this isn't a valid Android binary XML document.
        return True
    pos = 8
    while pos + 8 <= len(data):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, pos)
        if chunk_size < header_size or pos + chunk_size > len(data):
            return True
        if chunk_type == 0x0102 and chunk_size >= 36:  # RES_XML_START_ELEMENT_TYPE
            name_idx = struct.unpack_from("<I", data, pos + 20)[0]
            element = strings[name_idx] if name_idx < len(strings) else ""
            if element in {"uses-permission", "uses-permission-sdk-23", "uses-permission-sdk-m"}:
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, pos + 24)
                first = pos + 16 + attr_start
                if attr_size < 20 or attr_count > 4096 or first + attr_size * attr_count > pos + chunk_size:
                    return True
                for i in range(attr_count):
                    off = first + i * attr_size
                    attr_name_idx, raw_value_idx = struct.unpack_from("<II", data, off + 4)
                    attr_name = strings[attr_name_idx] if attr_name_idx < len(strings) else ""
                    value = strings[raw_value_idx] if raw_value_idx != 0xffffffff and raw_value_idx < len(strings) else ""
                    if not value and off + 20 <= pos + chunk_size:
                        value_type = data[off + 15]
                        value_data = struct.unpack_from("<I", data, off + 16)[0]
                        if value_type == 0x03 and value_data < len(strings):
                            value = strings[value_data]
                    if attr_name == "name" and value == permission:
                        return True
        pos += chunk_size
    return False


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: audit_release_apk.py <release.apk>", file=sys.stderr)
        return 2
    apk = Path(sys.argv[1])
    if not apk.is_file():
        print(f"FAIL APK not found: {apk}", file=sys.stderr)
        return 2
    report, failures = [], []
    def check(ok: bool, msg: str) -> None:
        report.append(("PASS " if ok else "FAIL ") + msg)
        if not ok:
            failures.append(msg)
    data = apk.read_bytes()
    report += [f"APK={apk}", f"SIZE={len(data)}", f"SHA256={hashlib.sha256(data).hexdigest()}"]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as outer:
            check(outer.testzip() is None, "APK ZIP integrity")
            names = set(outer.namelist())
            xop_config_name = "assets/protector/config.json"
            if xop_config_name not in names:
                # The unsigned baseline is audited before XopProtector runs, so
                # its config cannot exist yet. Require it only for the final/XOP
                # audit; this keeps the baseline gate meaningful without
                # weakening the post-XOP gate.
                check(False, "Xop protector config packaged" if REQUIRE_XOP_PROVENANCE
                      else "Xop protector config deferred to final XOP packaging")
            else:
                try:
                    xop_config = json.loads(outer.read(xop_config_name).decode("utf-8"))
                except (ValueError, UnicodeError, KeyError):
                    xop_config = None
                check(isinstance(xop_config, dict), "Xop protector config is valid JSON")
                if isinstance(xop_config, dict):
                    check(xop_config.get("protect_so") is True, "Xop native SO protection enabled")
                    check(xop_config.get("detect_proxy") is True and xop_config.get("net_guard") is True,
                          "Xop proxy detection and NetGuard enabled")
                    check(xop_config.get("so_decrypt_mode") == "lazy", "Xop SO decryption uses lazy mode")
                    check(xop_config.get("rasp_action") == 2, "Xop RASP enforce action enabled")
                    for hmac_name in ("dex_hmac", "code_hmac", "code_methods_hmac"):
                        check(bool(re.fullmatch(r"[0-9a-f]{64}", str(xop_config.get(hmac_name, "")))),
                              f"Xop {hmac_name} is a populated SHA-256 HMAC")
                    check(bool(re.fullmatch(r"[0-9a-f]{64}", str(xop_config.get("app_sign_sha256", "")))),
                          "Xop application signing certificate fingerprint is populated")
                    report.append("INFO insns_xor_key is a legacy field; native instruction protection is AES-GCM")
                    check(xop_config.get("encrypt_assets") is True, "Xop asset encryption enabled")
                    report.append("INFO Xop asset encryption excludes Chaquopy app.imy and engine license metadata by CI policy")
            version_metadata = sorted(
                n for n in names
                if n.startswith("META-INF/") and n.lower().endswith(".version")
            )
            check(not version_metadata,
                  "dependency version metadata absent from APK" if not version_metadata
                  else "dependency version metadata remains: " + ", ".join(version_metadata))
            forbidden_package_names = {"rebrand_config.txt", "app-metadata.properties"}
            packaged_forbidden = sorted(n for n in names if Path(n).name.lower() in forbidden_package_names)
            check(not packaged_forbidden,
                  "sensitive local rebrand/build metadata absent from APK" if not packaged_forbidden
                  else "forbidden APK metadata entries: " + ", ".join(packaged_forbidden))
            check("lib/arm64-v8a/librasp_guard.so" in names, "native RASP library packaged")
            unluac_entry = "lib/arm64-v8a/libunluac-cli.so"
            check(unluac_entry in names, "Android ARM64 Smart Lua native decompiler packaged")
            check("assets/engine_licenses/unluac-rs-MIT.txt" in names,
                  "unluac-rs MIT license attribution packaged")
            if unluac_entry in names:
                native_cli = outer.read(unluac_entry)
                is_arm64_elf = (
                    len(native_cli) > 20 and native_cli[:4] == b"\x7fELF"
                    and native_cli[18:20] == b"\xb7\x00"
                    and b"/system/bin/linker64\x00" in native_cli
                )
                check(is_arm64_elf, "unluac-rs executable is Android ARM64 ELF")
                manifest_name = "assets/engine_licenses/unluac-rs-android-arm64.manifest"
                checksum_name = "assets/engine_licenses/unluac-rs-android-arm64.sha256"
                check(manifest_name in names and checksum_name in names,
                      "unluac-rs Android build provenance and checksum packaged")
                if manifest_name in names:
                    manifest = outer.read(manifest_name).decode("utf-8", errors="replace")
                    check("tag=v1.4.4" in manifest and "target=aarch64-linux-android" in manifest,
                          "unluac-rs pinned release/target provenance verified")
                    provenance_recorded = (
                        re.search(r"(?m)^source_sha256=[0-9a-f]{64}$", manifest) is not None
                        and re.search(r"(?m)^xop_protected_sha256=[0-9a-f]{64}$", manifest) is not None
                    )
                    check(provenance_recorded or not REQUIRE_XOP_PROVENANCE,
                          "unluac-rs original and XOP-protected hashes recorded"
                          if REQUIRE_XOP_PROVENANCE else
                          "unluac-rs XOP provenance deferred to final XOP packaging")
                if checksum_name in names:
                    checksum_parts = outer.read(checksum_name).decode("ascii", errors="ignore").split()
                    expected_hash = checksum_parts[0] if checksum_parts else ""
                    check(expected_hash == hashlib.sha256(native_cli).hexdigest(),
                          "unluac-rs Android executable checksum verified")
            luau_entry = "lib/arm64-v8a/libluau-decompiler-cli.so"
            check(luau_entry in names, "Android ARM64 Luau v3-v9 decompiler packaged")
            check("assets/engine_licenses/luau-decompiler-MIT.txt" in names,
                  "PumbaaDev Luau decompiler MIT license attribution packaged")
            if luau_entry in names:
                luau_native = outer.read(luau_entry)
                is_luau_arm64_elf = (
                    len(luau_native) > 20 and luau_native[:4] == b"\x7fELF"
                    and luau_native[18:20] == b"\xb7\x00"
                    and b"/system/bin/linker64\x00" in luau_native
                )
                check(is_luau_arm64_elf, "Luau decompiler executable is Android ARM64 ELF")
                manifest_name = "assets/engine_licenses/luau-decompiler-android-arm64.manifest"
                checksum_name = "assets/engine_licenses/luau-decompiler-android-arm64.sha256"
                check(manifest_name in names and checksum_name in names,
                      "PumbaaDev Android build provenance and checksum packaged")
                if manifest_name in names:
                    manifest = outer.read(manifest_name).decode("utf-8", errors="replace")
                    check("commit=ee07098c31e11601a9ca434bc12932a4ded65f7b" in manifest
                          and "supported_luau_bytecode=3-9" in manifest,
                          "PumbaaDev pinned commit/compatibility provenance verified")
                    provenance_recorded = (
                        re.search(r"(?m)^source_sha256=[0-9a-f]{64}$", manifest) is not None
                        and re.search(r"(?m)^xop_protected_sha256=[0-9a-f]{64}$", manifest) is not None
                    )
                    check(provenance_recorded or not REQUIRE_XOP_PROVENANCE,
                          "Luau original and XOP-protected hashes recorded"
                          if REQUIRE_XOP_PROVENANCE else
                          "Luau XOP provenance deferred to final XOP packaging")
                if checksum_name in names:
                    checksum_parts = outer.read(checksum_name).decode("ascii", errors="ignore").split()
                    expected_hash = checksum_parts[0] if checksum_parts else ""
                    check(expected_hash == hashlib.sha256(luau_native).hexdigest(),
                          "PumbaaDev Android executable checksum verified")
            check("assets/chaquopy/app.imy" in names, "Chaquopy app bundle packaged")
            nx_index_plain = "assets/nx/i.dat" in names
            nx_index_xop = "assets/protector/aenc/nx/i.dat" in names
            check(nx_index_plain or nx_index_xop,
                  "sealed JAR index packaged" if (nx_index_plain or nx_index_xop) else "sealed JAR index missing")
            check(not any(n.startswith("assets/unluac/") and n.lower().endswith(".jar") for n in names),
                  "plaintext unluac JAR assets absent")
            if nx_index_xop:
                check("assets/protector/assets.map" in names, "Xop encrypted asset index packaged")
                check("assets/protector/aenc/nx/i.dat" in names, "Xop PAS1 encrypted sealed JAR index packaged")
            vcs_entries = sorted(n for n in names if n.endswith("version-control-info.textproto"))
            check(not vcs_entries, "VCS revision metadata absent" if not vcs_entries else "VCS revision metadata absent; found: " + ", ".join(vcs_entries))
            dex_names = sorted(n for n in names if re.fullmatch(r"classes(?:[0-9]+)?\.dex", n))
            dex_bytes = b"".join(outer.read(n) for n in dex_names)
            check(b"ALVISIA-20261010-MAIN-SEAL1" not in dex_bytes,
                  "sealed build ID absent from plaintext DEX")
            check(b"com/securevale/" not in dex_bytes,
                  "recognizable SecureVale SDK classes absent from DEX")
            manifest = outer.read("AndroidManifest.xml") if "AndroidManifest.xml" in names else b""
            check(bool(manifest), "compiled Android manifest exists")
            # Resource shrinking may rename compiled res/ paths; verify packaged MP3 payloads.
            audio_entries = sorted(
                n for n in names
                if n.startswith("res/") and n.lower().endswith(".mp3")
            )
            named_background = [n for n in audio_entries if n.lower().endswith("/bgm_pulse.mp3")]
            audio_present = bool(named_background) or len(audio_entries) >= 2
            check(audio_present, "background audio resource packaged" if audio_present else "background audio resource missing from APK")
            for audio_name in audio_entries:
                check(outer.getinfo(audio_name).file_size > 0, f"non-empty media asset: {audio_name}")
            has_dump_permission = _manifest_declares_permission(manifest, "android.permission.DUMP")
            check(not has_dump_permission,
                  "compiled manifest excludes android.permission.DUMP")
            check(b"android.permission.DELETE_PACKAGES" not in manifest,
                  "compiled manifest excludes unused DELETE_PACKAGES")
            check(b"android.permission.CHANGE_NETWORK_STATE" not in manifest,
                  "compiled manifest excludes unused CHANGE_NETWORK_STATE")
            # READ_PHONE_STATE is currently declared for legacy device/tool compatibility.
            # Do not fail the release audit merely because that declared permission is present;
            # any future permission removal must be verified against PermissionHelper/tool usage.
            report.append("INFO compiled manifest READ_PHONE_STATE presence recorded; permission policy is source-reviewed")
            blobs_plain = sorted(n for n in names if n.startswith("assets/nx/") and n.endswith(".bin"))
            blobs_xop = sorted(n for n in names if n.startswith("assets/protector/aenc/nx/") and n.endswith(".bin"))
            blobs = blobs_xop if blobs_xop else blobs_plain
            check(len(blobs) >= 3, f"sealed JAR asset count >= 3 (found {len(blobs)})")
            if blobs_xop:
                for n in blobs_xop:
                    check(outer.read(n).startswith(b"PAS1"), f"Xop PAS1 sealed JAR header: {n}")
            else:
                for n in blobs_plain:
                    check(outer.read(n).startswith(ASSET_MAGIC), f"sealed JAR header: {n}")
            index = outer.read("assets/nx/i.dat") if "assets/nx/i.dat" in names else b""
            if index:
                check(index.startswith(ASSET_MAGIC), "sealed JAR index header")
            imy = outer.read("assets/chaquopy/app.imy") if "assets/chaquopy/app.imy" in names else b""
            try:
                with zipfile.ZipFile(io.BytesIO(imy)) as inner:
                    check(inner.testzip() is None, "Chaquopy app.imy ZIP integrity")
                    check(not any("version-control-info.textproto" in n for n in inner.namelist()), "VCS metadata absent from Chaquopy bundle")
                    members = inner.namelist()
                    forbidden_inner = sorted(n for n in members if Path(n).name.lower() in forbidden_package_names)
                    check(not forbidden_inner,
                          "sensitive local rebrand/build metadata absent from app.imy" if not forbidden_inner
                          else "forbidden app.imy metadata entries: " + ", ".join(forbidden_inner))
                    # These implementation markers must not be exposed in plaintext
                    # DEX or Python source. Encrypted .alv payloads are deliberately
                    # excluded from this static-string check.
                    plain_python = b"\\n".join(
                        inner.read(n) for n in members if n.lower().endswith(".py")
                    )
                    protected_markers = (b"Feistel-like", b"vm_extract_payload")
                    exposed = [marker.decode("ascii") for marker in protected_markers
                               if marker in dex_bytes or marker in plain_python]
                    check(not exposed,
                          "custom cipher/deobfuscator markers absent from plaintext code" if not exposed
                          else "plaintext protection markers exposed: " + ", ".join(exposed))
                    by_base = {Path(n).name: n for n in members}
                    bridge_name = by_base.get("alvsia_bridge.py")
                    bridge_bytes = inner.read(bridge_name) if bridge_name else b""
                    check(bool(bridge_bytes) and len(bridge_bytes) < 2000,
                          "plaintext bridge is a small bootstrap stub")
                    check(b"import alvsia_bridge_impl as impl" in bridge_bytes and b"if mid == 1" not in bridge_bytes,
                          "tool routing is not shipped in plaintext bridge")
                    actual_sealed = {Path(n).name for n in members if n.lower().endswith(".alv")}
                    missing = sorted(EXPECTED_SEALED - actual_sealed)
                    unexpected = sorted(actual_sealed - EXPECTED_SEALED)
                    check(not missing and not unexpected, "all protected Python payloads exist" if not missing else "missing sealed payloads: " + ", ".join(missing))
                    check(not unexpected, "no unreviewed sealed payloads" if not unexpected else "unexpected sealed payloads: " + ", ".join(unexpected))
                    for name in sorted(EXPECTED_SEALED & actual_sealed):
                        check(inner.read(by_base[name]).startswith(SEAL_MAGIC), f"AES-GCM payload header: {name}")
                    plaintext = []
                    for name in members:
                        normalized = name.replace("\\", "/").lower().lstrip("./")
                        base = Path(normalized).name
                        for module in PROTECTED_MODULES:
                            module = module.lower()
                            parent, _, leaf = module.rpartition("/")
                            source_match = (
                                base == leaf + ".py"
                                or base == leaf + ".pyc"
                                or re.fullmatch(re.escape(leaf) + r"\.[a-z0-9_-]+\.pyc", base) is not None
                            )
                            parent_match = not parent or ("/" + parent + "/") in ("/" + normalized + "/")
                            if source_match and parent_match:
                                plaintext.append(name)
                                break
                    check(not plaintext, "protected Python source/bytecode absent as plaintext" if not plaintext else "plaintext protected modules: " + ", ".join(plaintext))
                    check(any(Path(n).name in {"sealed_loader.py", "sealed_loader.pyc"} for n in members),
                          "sealed Python loader packaged")
            except (zipfile.BadZipFile, OSError) as exc:
                check(False, f"Chaquopy app.imy unreadable: {exc}")
    except (zipfile.BadZipFile, OSError) as exc:
        check(False, f"APK archive unreadable: {exc}")
    report.append("RESULT=" + ("FAIL" if failures else "PASS"))
    text = "\n".join(report) + "\n"
    print(text, end="")
    Path("release_security_audit.txt").write_text(text, encoding="utf-8")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())