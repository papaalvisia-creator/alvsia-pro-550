"""Static regression checks for the 19-module Android tool menu/bridge contract."""
from pathlib import Path
from typing import Optional, Tuple
import re
import ast
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MENUS = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
BRIDGE = ROOT / "app/src/main/python/alvsia_bridge.py"
BRIDGE_IMPL = ROOT / "app/src/main/python/alvsia_bridge_impl.py"
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt"
ENGINE = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolEngine.kt"
ULTIMATE = ROOT / "app/src/main/python/alvsia_ultimate.py"
RUNNER = ROOT / "app/src/main/java/com/alvsia/pro/tool/PythonBridgeRunner.kt"
WORKSPACE = ROOT / "app/src/main/java/com/alvsia/pro/ui/tool/ToolWorkspaceScreen.kt"
OUTPUT_BROWSER = ROOT / "app/src/main/java/com/alvsia/pro/ui/output/OutputBrowserScreen.kt"



def test_python_auth_normalizes_java_string_and_lua_avoids_art_oom():
    bridge = (ROOT / "app/src/main/python/alvsia_bridge.py").read_text(encoding="utf-8")
    unluac = (ROOT / "app/src/main/java/com/alvsia/pro/tool/UnluacRunner.kt").read_text(encoding="utf-8")
    impl = (ROOT / "app/src/main/python/alvsia_bridge_impl.py").read_text(encoding="utf-8")
    # configure_runtime must normalise the incoming token (which may arrive as a
    # Chaquopy PyObject wrapping a Java String) before passing it to the gate.
    # The original str(token) was replaced by a robust _extract_str() helper that
    # handles Java-proxy repr leakage; check for either pattern.
    assert ("token = str(token)" in bridge or "_extract_str" in bridge), \
        "configure_runtime must normalise the incoming token from a potential Chaquopy PyObject"
    assert "gate.isTokenCurrent(token)" in bridge
    # SessionGate is loaded from Python by its fully-qualified JVM name; R8 must not rename/repackage it.
    rules = (ROOT / "app/proguard-rules.pro").read_text(encoding="utf-8")
    assert "-keep class com.alvsia.pro.sec.SessionGate { *; }" in rules
    assert 'getattr(exc, "name"' not in bridge, "release bridge must not expose internal exception/module diagnostics"
    assert '_CD="error"' in bridge, "failed runtime configuration must return a generic diagnostic"
    configure = bridge.split("def configure_runtime", 1)[1].split("def run_tool", 1)[0]
    assert "gate.isSessionAuthorized()" not in configure, "split auth checks can race with RASP session locking"
    gate = (ROOT / "app/src/main/java/com/alvsia/pro/sec/SessionGate.kt").read_text(encoding="utf-8")
    assert "fun isTokenCurrent(candidate: String): Boolean = synchronized(this)" in gate
    assert "fun lock(@Suppress(\"UNUSED_PARAMETER\") ctx: Context)" in gate
    lock_body = gate.split("fun lock(@Suppress(\"UNUSED_PARAMETER\") ctx: Context)", 1)[1].split("\n    }", 1)[0]
    assert "synchronized(this)" in lock_body, "RASP lock must serialize with Python token validation"
    assert "ART_SAFE_LIMIT = 1L * 1024L * 1024L" in unluac
    lua_branch = impl.split("# ── 5  LUA Tools", 1)[1].split('if sid == "lua_analyze":', 1)[0]
    assert "stream_result = decompile_large(Path(ip), dest_lua, jars_dir=jars)" in lua_branch
    assert lua_branch.index("stream_result = decompile_large") < lua_branch.index("r = feat.run_lua_smart")
    assert "if in_size > 1 * 1024 * 1024:" not in lua_branch

def test_menu_ids_are_unique_and_reachable():
    menus = MENUS.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8") + "\n" + BRIDGE_IMPL.read_text(encoding="utf-8")
    ids = re.findall(r'SubTool\(\s*"([a-zA-Z0-9_]+)"', menus)
    assert ids, "No SubTool IDs found; menu parsing may have drifted"
    duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
    assert not duplicates, f"Duplicate sub-tool IDs: {duplicates}"

    generic = {
        "pak_delete_entry": '"delete" in sid',
        "pak_inject": 'sid in ("pak_repack_full","pak_inject","pak_encrypt","pak_decrypt_restore")',
        "pak_full_unpack": 'sid.startswith("pak_full")',
        "lua_patch_byte": 'mid == 16 or sid.startswith("lua_patch_")',
        "lua_mod_repack": 'sid.startswith("lua_patch_") or sid in ("lua_inject_hook","lua_mod_repack")',
    }
    direct_engine_routes = {"android_permission_dump": 'subId == "android_permission_dump"'}
    engine = ENGINE.read_text(encoding="utf-8")
    missing = []
    for sid in ids:
        if sid in direct_engine_routes and direct_engine_routes[sid] in engine:
            continue
        if f'"{sid}"' in bridge:
            continue
        route = generic.get(sid)
        if not route or route not in bridge:
            missing.append(sid)
    assert not missing, f"Menu IDs without bridge routes: {missing}"


def test_frida_spawn_preserves_full_package_name():
    tree = ast.parse(ULTIMATE.read_text(encoding="utf-8"), filename=str(ULTIMATE))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "frida_spawn_trace"
    )
    isolated = ast.Module(body=[fn], type_ignores=[])
    namespace = {}
    exec(compile(isolated, str(ULTIMATE), "exec"), namespace)
    with tempfile.TemporaryDirectory() as td:
        result = namespace["frida_spawn_trace"]("com.tencent.ig", td)
        assert result.get("ok"), result
        output = Path(result["out"]).read_text(encoding="utf-8")
        assert "-f com.tencent.ig " in output, output
        assert "-f com.tencent " not in output, output


def test_catalog_contains_all_nineteen_modules():
    catalog = CATALOG.read_text(encoding="utf-8")
    ids = [int(x) for x in re.findall(r'ToolItem\((\d+),', catalog)]
    assert ids == list(range(1, 20)), f"Expected module IDs 1..19 in order, got {ids}"
    assert 'ToolItem(19, "ALVSIA PRIVATE TOOL"' in catalog


def test_private_module_19_menu_and_dispatch_contract():
    menus = MENUS.read_text(encoding="utf-8")
    catalog = CATALOG.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8") + "\n" + BRIDGE_IMPL.read_text(encoding="utf-8")
    assert '19 -> "ALVSIA PRIVATE TOOL"' in menus
    private_menu = menus.split("// Module 19 — ALVSIA PRIVATE TOOL", 1)[1].split("\n    )", 1)[0]
    private_ids = re.findall(r'SubTool\(\s*"([a-zA-Z0-9_]+)"', private_menu)
    expected = [
        "priv_zuc_decrypt", "priv_aes_scan", "priv_xor_recover",
        "priv_lua_parse", "priv_lua_convert", "priv_lua_heping",
        "priv_compress_fit", "priv_apk_audit", "priv_apk_manifest",
        "priv_str_recover", "priv_entropy_map", "priv_pak_manifest",
    ]
    assert private_ids == expected, f"Module 19 menu changed unexpectedly: {private_ids}"
    missing = [sid for sid in expected if f'"{sid}"' not in bridge]
    assert not missing, f"Module 19 items lack bridge dispatch routes: {missing}"
    assert "sealed runtime required" in menus.lower()


def test_engine_surfaces_bridge_failures():
    engine = ENGINE.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8") + "\n" + BRIDGE_IMPL.read_text(encoding="utf-8")
    assert "X OUT -> operation failed" in engine
    runner = RUNNER.read_text(encoding="utf-8")
    assert "explicitFalse" in runner
    assert 'startsWith("X ")' in runner
    assert "target filename(s) are not present in this PAK index" in bridge
    assert "Lua filenames sample ->" in bridge


def test_tool_argument_and_storage_contracts():
    engine = ENGINE.read_text(encoding="utf-8")
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    workspace = WORKSPACE.read_text(encoding="utf-8")
    output_browser = OUTPUT_BROWSER.read_text(encoding="utf-8")
    assert "custom_keys=keys" not in bridge
    assert 'ult.decrypt_auto(ip, dest_dec, str(work_dir()))' in bridge
    assert 'ult.lua_inject_hook(ip, dest_inj, str(hf))' in bridge
    assert 'ult.pak_deep_zuc(ip, dest_pakd, key_hex, iv_hex)' in bridge
    assert "WorkPaths.dirWork()" in workspace
    assert "WorkPaths.dirOut()" in output_browser
    assert "explicitTrue" in runner
    assert runner.count('getMethod("get", Any::class.java)') == 2
    assert 'getMethod("get", String::class.java)' not in runner
    assert "moduleId !in listOf(7, 13, 15)" not in engine
    assert 'return subId !in setOf("frida_js_dump", "frida_spawn", "xor_batch")' in engine
    config_schema = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SubToolConfig.kt").read_text(encoding="utf-8")
    assert '"frida_js_dump", "frida_spawn" -> listOf(' in config_schema
    assert '"frida_jni_hook", "frida_spawn" -> listOf(' not in config_schema


def test_bridge_call_signatures_match_helpers():
    source_paths = {
        "core": ROOT / "app/src/main/python/alvsia_core.py",
        "feat": ROOT / "app/src/main/python/alvsia_features.py",
        "ult": ROOT / "app/src/main/python/alvsia_ultimate.py",
    }
    helpers = {}
    for alias, path in source_paths.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        helpers[alias] = {
            node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    bridge_tree = ast.parse(BRIDGE_IMPL.read_text(encoding="utf-8"), filename=str(BRIDGE_IMPL))
    errors = []
    for node in ast.walk(bridge_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if not isinstance(owner, ast.Name) or owner.id not in helpers:
            continue
        alias, name = owner.id, node.func.attr
        fn = helpers[alias].get(name)
        if fn is None:
            errors.append(f"{alias}.{name}: helper definition not found")
            continue

        argspec = fn.args
        positional = list(argspec.posonlyargs) + list(argspec.args)
        kwonly = [arg.arg for arg in argspec.kwonlyargs]
        has_varargs = argspec.vararg is not None
        has_kwargs = argspec.kwarg is not None
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            continue
        supplied_pos = len(node.args)
        if supplied_pos > len(positional) and not has_varargs:
            errors.append(f"{alias}.{name}: too many positional args ({supplied_pos}>{len(positional)})")
            continue
        keyword_names = {kw.arg for kw in node.keywords if kw.arg is not None}
        valid_names = set(arg.arg for arg in positional) | set(kwonly)
        if not has_kwargs:
            invalid = sorted(keyword_names - valid_names)
            if invalid:
                errors.append(f"{alias}.{name}: unsupported keyword(s) {invalid}")
        default_count = len(argspec.defaults)
        required_positional = positional[:len(positional) - default_count]
        supplied_names = {arg.arg for arg in positional[:supplied_pos]} | keyword_names
        missing = [arg.arg for arg in required_positional if arg.arg not in supplied_names]
        for arg, default in zip(kwonly, argspec.kw_defaults):
            if default is None and arg not in keyword_names:
                missing.append(arg)
        if missing:
            errors.append(f"{alias}.{name}: missing required argument(s) {missing}")

    assert not errors, "Bridge/helper call contract mismatches:\n" + "\n".join(errors)


def test_obb_extract_normalizes_archive_paths():
    source = (ROOT / "app/src/main/python/alvsia_features.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_obb_extract")
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ROOT / "app/src/main/python/alvsia_features.py"), "exec"), namespace)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        archive, out = base / "sample.zip", base / "out"
        import zipfile
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("folder\\\\file.txt", "hello")
        result = namespace["run_obb_extract"](archive, out)
        assert result.get("ok"), result
        assert (out / "folder" / "file.txt").read_text(encoding="utf-8") == "hello"


def test_run_unzip_rejects_zip_slip_and_extracts_safe_entries():
    source = (ROOT / "app/src/main/python/alvsia_features.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_unzip")
    import shutil
    import zipfile
    namespace = {"Path": Path, "zipfile": zipfile, "shutil": shutil}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ROOT / "app/src/main/python/alvsia_features.py"), "exec"), namespace)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        archive, out = base / "safe.zip", base / "out"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("nested/ok.txt", "safe")
        result = namespace["run_unzip"](archive, out)
        assert result.get("ok") and (out / "nested" / "ok.txt").read_text(encoding="utf-8") == "safe"

        malicious, out2 = base / "malicious.zip", base / "out2"
        with zipfile.ZipFile(malicious, "w") as zf:
            zf.writestr("../escaped.txt", "outside")
        try:
            namespace["run_unzip"](malicious, out2)
        except ValueError as exc:
            assert "unsafe ZIP entry path" in str(exc)
        else:
            raise AssertionError("ZIP path traversal was not rejected")
        assert not (base / "escaped.txt").exists()


def test_large_lua_source_is_detected_before_bytecode_fallback():
    source = (ROOT / "app/src/main/python/lua_engine/streaming_decompiler.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_comment_prefix_lua_magic")
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "preflight_magic")
    namespace = {"Path": Path, "re": re, "Optional": Optional, "Tuple": Tuple}
    exec(compile(ast.Module(body=[helper, fn], type_ignores=[]), "streaming_decompiler.py", "exec"), namespace)
    with tempfile.TemporaryDirectory() as td:
        sample = Path(td) / "primary_BRPlayerCharacterBase.lua"
        sample.write_text("local function main()\n  return true\nend\n" + ("-- filler\n" * 700000), encoding="utf-8")
        assert sample.stat().st_size > 5 * 1024 * 1024
        assert namespace["preflight_magic"](sample) == "source"


def test_large_file_helpers_stream_and_report_hashes():
    source = (ROOT / "app/src/main/python/alvsia_features.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {"run_strings_scan", "run_export_report"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in functions} == names
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT / "app/src/main/python/alvsia_features.py"), "exec"), namespace)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        sample = base / "sample.bin"
        sample.write_bytes(b"alpha-string\x00beta-string\x00alpha-string")
        scan = namespace["run_strings_scan"](sample, base / "scan")
        assert scan.get("ok"), scan
        output = Path(scan["out"]).read_text(encoding="utf-8")
        assert output.splitlines() == ["alpha-string", "beta-string"]
        report = namespace["run_export_report"](sample, base / "report")
        assert report.get("ok"), report
        import hashlib
        expected = hashlib.sha256(sample.read_bytes()).hexdigest()
        assert report.get("sha256") == expected, report
        assert expected in Path(report["out"]).read_text(encoding="utf-8")


def test_profile_catalog_matches_canonical_nineteen_modules():
    profile_path = ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt"
    profile = profile_path.read_text(encoding="utf-8")
    chips = re.findall(r'ModuleChip\(\s*"[^"]+"\s*,\s*"([^"]+)"\s*\)', profile)
    assert len(chips) == 19, f"Expected 19 profile chips, got {len(chips)}"
    assert chips[-1] == "ALVSIA PRIVATE TOOL"
    assert '_ActionTile("✦", "CREATOR", "ALVSIA_PRO"' in profile
    assert '_InfoTile("MODULES", "19"' in profile
    catalog = CATALOG.read_text(encoding="utf-8")
    names = re.findall(r'ToolItem\(\s*\d+\s*,\s*"([^"]+)"', catalog)
    assert names == chips, f"Home/profile module names differ: home={names}, profile={chips}"


def test_reference_inspection_subtools_are_registered_and_read_only():
    menus = MENUS.read_text(encoding="utf-8")
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    helper = (ROOT / "app/src/main/python/alvsia_reference_tools.py").read_text(encoding="utf-8")
    for sid in ("lua_format_probe", "anti_re_source_triage", "so_dump_audit"):
        assert sid in menus
        assert sid in bridge
    assert "probe_lua_file" in helper
    assert "scan_source_file" in helper
    assert "inspect_dump_file" in helper
    assert "execution_performed" in helper
    assert "memory_acquisition" in helper
    assert "subprocess.run(" not in helper
    assert "ptrace(" not in helper
    assert "process_vm_readv(" not in helper


def test_reference_inspection_helpers_smoke():
    import importlib.util
    helper_path = ROOT / "app/src/main/python/alvsia_reference_tools.py"
    spec = importlib.util.spec_from_file_location("alvsia_reference_tools", str(helper_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lua = root / "sample.luac"
        lua.write_bytes(b"\x1bLua\x53\x00" + (b"\x00" * 40))
        assert module.probe_lua_file(lua)["format"] == "Lua 5.3"
        source = root / "sample.py"
        source.write_text("import base64\nexec(payload)\n", encoding="utf-8")
        findings = module.scan_source_file(source)["findings"]
        assert any(item["indicator"] == "dynamic_execution" for item in findings)
        dump = root / "sample.dmp"
        dump.write_bytes((b"\x00" * 5000) + b"HELLO_WORLD" + (b"\x00" * 100))
        report = module.inspect_dump_file(dump, block_size=4096)
        assert report["size"] == dump.stat().st_size
        assert report["strings"]
        assert report["memory_acquisition"] is False
        assert report["secret_extraction"] is False

def test_pak_integrity_audit_is_registered_and_read_only():
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    menus = MENUS.read_text(encoding="utf-8")
    core = (ROOT / "app/src/main/python/alvsia_core.py").read_text(encoding="utf-8")
    assert "pak_deep_integrity_audit" in bridge
    assert "pak_deep_integrity_audit" in menus
    assert "def run_pak_integrity_audit(" in core
    assert "slot_fingerprint_sha256" in core
    assert "invalid_ranges" in core
    assert "overlaps" in core
    assert "Original PAK was not modified" in bridge

def test_obb_integrity_audit_is_registered_and_read_only():
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    menus = MENUS.read_text(encoding="utf-8")
    helper = (ROOT / "app/src/main/python/alvsia_reference_tools.py").read_text(encoding="utf-8")
    assert "obb_integrity_audit" in bridge
    assert "obb_integrity_audit" in menus
    assert "def audit_archive_file(" in helper
    assert "archive.open(info, \"r\")" in helper
    assert "extractall(" not in helper


def test_reference_inspectors_format_and_archive_fixtures():
    import importlib.util
    import zipfile
    helper_path = ROOT / "app/src/main/python/alvsia_reference_tools.py"
    spec = importlib.util.spec_from_file_location("alvsia_reference_tools_fixtures", str(helper_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lj = root / "sample.lj"
        lj.write_bytes(b"\x1bLJ" + b"\x00" * 24)
        assert module.probe_lua_file(lj)["format"] == "LuaJIT bytecode"

        good = root / "good.obb"
        with zipfile.ZipFile(str(good), "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("assets/data.bin", b"ALVSIA-OBB-TEST")
        good_report = module.audit_archive_file(good)
        assert good_report["ok"] is True
        assert good_report["crc_checked_bytes"] == len(b"ALVSIA-OBB-TEST")
        assert good_report["crc_coverage_complete"] is True

        unsafe = root / "unsafe.obb"
        with zipfile.ZipFile(str(unsafe), "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("../outside.txt", b"blocked")
        unsafe_report = module.audit_archive_file(unsafe)
        assert unsafe_report["ok"] is False
        assert unsafe_report["unsafe_paths"] == ["../outside.txt"]

        limited_report = module.audit_archive_file(good, max_total_bytes=1)
        assert limited_report["ok"] is False
        assert limited_report["crc_coverage_complete"] is False
        assert limited_report["skipped_crc"]


def test_xor_known_vector_selftest_is_registered():
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    menus = MENUS.read_text(encoding="utf-8")
    assert "xor_selftest" in bridge
    assert "xor_selftest" in menus
    assert "9fe1e8bc97ec9eb791ff9e8ab0cad781bb8dcd8ab2cb939bbbdecacfa89c" in bridge
    assert 'sid not in ("xor_batch", "xor_selftest")' in bridge


def test_decrypt_known_answer_selftest_is_registered():
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    menus = MENUS.read_text(encoding="utf-8")
    assert "dec_selftest" in bridge
    assert "dec_selftest" in menus
    assert "69c4e0d86a7b0430d8cdb78070b4c55a" in bridge
    assert "7649abac8119b246cee98e9b12e9197d" in bridge
    assert "NIST AES known-answer tests" in bridge

if __name__ == "__main__":
    tests = (
        test_python_auth_normalizes_java_string_and_lua_avoids_art_oom,
        test_menu_ids_are_unique_and_reachable,
        test_catalog_contains_all_nineteen_modules,
        test_private_module_19_menu_and_dispatch_contract,
        test_frida_spawn_preserves_full_package_name,
        test_engine_surfaces_bridge_failures,
        test_tool_argument_and_storage_contracts,
        test_profile_catalog_matches_canonical_nineteen_modules,
        test_bridge_call_signatures_match_helpers,
        test_obb_extract_normalizes_archive_paths,
        test_large_lua_source_is_detected_before_bytecode_fallback,
        test_run_unzip_rejects_zip_slip_and_extracts_safe_entries,
        test_large_file_helpers_stream_and_report_hashes,
        test_reference_inspection_subtools_are_registered_and_read_only,
        test_reference_inspection_helpers_smoke,
        test_pak_integrity_audit_is_registered_and_read_only,
        test_obb_integrity_audit_is_registered_and_read_only,
        test_reference_inspectors_format_and_archive_fixtures,
        test_xor_known_vector_selftest_is_registered,
        test_decrypt_known_answer_selftest_is_registered,
    )
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"TOOL DISPATCH TEST: PASS ({len(tests)}/{len(tests)})")







def test_private_module_19_uses_dedicated_workspace_paths():
    paths = (ROOT / "app/src/main/java/com/alvsia/pro/tool/WorkPaths.kt").read_text(encoding="utf-8")
    bridge = BRIDGE_IMPL.read_text(encoding="utf-8")
    assert '19 -> "ALVSIA_PRIVATE"' in paths
    assert "for (id in 1..19)" in paths
    assert 'dest = out_dir("ALVSIA_PRIVATE")' in bridge
