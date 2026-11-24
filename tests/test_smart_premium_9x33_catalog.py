from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
ROUTER = ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt"
CATALOG_TEXT = CATALOG.read_text(encoding="utf-8")
ROUTER_TEXT = ROUTER.read_text(encoding="utf-8")

EXPECTED = {
    1: ["apk_structure_inspector", "apk_manifest_permission_audit", "apk_dex_bytecode_inspector", "apk_resource_table_inspector", "apk_compare_resource_diff", "apk_signature_integrity_verify"],
    2: ["pak_profile_fingerprint", "pak_explorer_info", "pak_extract_unpak", "pak_selective_extract", "pak_entry_compare_replace", "pak_rebuild_repack", "pak_compact_rebuild_verify"],
    3: ["obb_format_inspector", "obb_extractor", "mini_obb_zsdic_adapter", "gamepatch_obb_repacker", "obb_integrity_pair_validator"],
    4: ["lua_smart_analyze", "lua_vm_version_detector", "lua_bytecode_inspector", "lua_smart_decompile", "lua_recovery_normalize", "lua_t24_bgmi_pubg_converter", "lua_protect_compile", "lua_custom_inject", "lua_round_trip_validator"],
    5: ["crypto_xor_multi_xor", "crypto_aes_candidate_transform", "crypto_sm4_engine", "crypto_zuc_engine", "crypto_key_pattern_scanner", "crypto_output_validator"],
    6: ["forensics_universal_file_detection", "forensics_file_signature_hash", "forensics_string_url_recovery", "forensics_entropy_region", "forensics_hex_structure_viewer", "forensics_evidence_report"],
    7: ["modding_uasset_uexp_inspector", "modding_ue4_string_id_extractor", "modding_skin_pair_finder", "modding_zsdic_analyzer", "modding_offset_size_fixer", "modding_resource_mapping_recovery"],
    8: ["native_elf_so_inspector", "native_strings_symbols", "native_abi_dependency_report", "native_xref_reference_analyzer", "native_authorized_runtime_trace"],
    9: ["workspace_file_manager", "workspace_recent_files_favorites", "workspace_batch_job_queue", "workspace_resume_cancel_progress", "workspace_output_browser_history"],
    10: ["lab_engine_registry", "lab_engine_self_test", "lab_regression_diff_compare", "lab_large_file_benchmark"],
}

def test_catalog_is_exactly_10x59():
    calls = re.findall(r'SubTool\(\s*"([^"]+)"([^\n]*)', CATALOG_TEXT)
    declared = [sid for sid, _ in calls]
    assert len(declared) == 59
    assert len(set(declared)) == 59
    assert [len(EXPECTED[i]) for i in range(1, 11)] == [6, 7, 5, 9, 6, 6, 6, 5, 5, 4]
    assert sum(map(len, EXPECTED.values())) == 59
    assert declared == [sid for i in range(1, 11) for sid in EXPECTED[i]]

def test_every_enabled_public_id_has_an_explicit_router_entry():
    calls = re.findall(r'SubTool\(\s*"([^"]+)"([^\n]*)', CATALOG_TEXT)
    enabled = [sid for sid, tail in calls if "enabled = false" not in tail]
    assert len(enabled) == 38
    native_routes = {
        "workspace_recent_files_favorites": '"workspace_recent_files_favorites" -> screen = "workspace"',
        "workspace_batch_job_queue": '"workspace_batch_job_queue" -> screen = "tasks"',
        "workspace_output_browser_history": '"workspace_output_browser_history" -> {',
    }
    main_activity = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
    missing = [
        sid for sid in enabled
        if not (
            native_routes[sid] in main_activity if sid in native_routes
            else f'"{sid}"' in ROUTER_TEXT
        )
    ]
    assert not missing, f"Enabled menu IDs without explicit backend/native routes: {missing}"

def test_unwired_items_are_disabled_and_not_fake_success_actions():
    calls = re.findall(r'SubTool\(\s*"([^"]+)"([^\n]*)', CATALOG_TEXT)
    pending = [sid for sid, tail in calls if "enabled = false" in tail]
    assert len(pending) == 21
    screen = (ROOT / "app/src/main/java/com/alvsia/pro/ui/tool/SubMenuScreen.kt").read_text(encoding="utf-8")
    assert ".clickable(enabled = item.enabled)" in screen
    assert 'else "PENDING"' in screen

def test_no_separate_ai_namespace_in_smart_catalog():
    assert "com.alvsia.ai.uncensored" not in CATALOG_TEXT
