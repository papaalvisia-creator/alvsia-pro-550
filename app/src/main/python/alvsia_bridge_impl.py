# -*- coding: utf-8 -*-
"""
ALVSIA PRO 5.5.2 — bridge for the 19-module catalog.
Modules 1-19 retain stable menu IDs and authenticated operation grants.
"""
from __future__ import annotations
import os
import re
import shutil
import traceback
import json
import hashlib
from pathlib import Path

# SECURITY: require native session marker plus 256-bit token shape (key login only).
# This is defense-in-depth, not a substitute for server-signed operation grants.

def _valid_apk_session():
    if os.environ.get("ALVSIA_APK_SESSION") != "1":
        return False
    try:
        from com.alvsia.pro.sec import SessionGate
        return bool(SessionGate.isSessionAuthorized())
    except Exception:
        return False

def run_tool(module_id, sub_id, input_path, out_root, engine_dir, jars_dir):
    lines = []
    try:
        # Hard gate
        if not _valid_apk_session():
            return "X AUTH: no valid APK session — login with your key first"
        lines.append("ALVSIA PRO 5.5.0 PREMIUM · engine")
        lines.append("m=%s sub=%s" % (module_id, sub_id))
        import alvsia_core as core
        import alvsia_features as feat

        out = Path(str(out_root))
        out.mkdir(parents=True, exist_ok=True)
        jars = Path(str(jars_dir)) if jars_dir else out / "jars"
        ip = str(input_path or "")
        mid = int(module_id)
        sid = str(sub_id)

        # Every tool dispatch requires a server-signed grant from the active Unaux panel.
        sid_l = sid.strip().lower()
        if sid_l.startswith("skin_obb"):
            grant_operation = "skin_obb"
        elif sid_l.startswith("game_patch"):
            grant_operation = "game_patch"
        elif sid_l in ("audit_apk", "apk_audit"):
            grant_operation = "apk_audit"
        elif sid_l.startswith(("priv_", "sm4_")) or sid_l in ("url_scan_so", "pubg_lua_convert"):
            grant_operation = "alvsia_private_tool"
        else:
            grant_operation = {
                1: "pak_tools", 2: "pak_tools", 3: "pak_tools", 4: "obb_tools",
                5: "lua_tools", 6: "file_scan", 7: "workspace", 8: "export_report",
                9: "rebrand", 10: "so_analyzer", 11: "frida_tracer", 12: "xor_suite",
                13: "decrypt_engine", 14: "pak_tools", 15: "string_recover",
                16: "lua_inject", 17: "anti_re_audit", 18: "lua_protector",
                19: "alvsia_private_tool"
            }.get(mid)
        if not grant_operation:
            return "X AUTH: module/subtool has no Unaux grant mapping"
        core._alvsia_require_operation((grant_operation,))

        def need_file():
            if not ip or not Path(ip).exists():
                lines.append("X input missing")
                return False
            return True

        def work_dir():
            d = out / "WORK"
            d.mkdir(parents=True, exist_ok=True)
            return d

        def read_config(name: str):
            """Read a simple key=value config, also accepting JSON objects."""
            path = work_dir() / name
            if not path.is_file():
                return {}
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
            if not raw:
                return {}
            if raw.startswith("{"):
                try:
                    value = json.loads(raw)
                    if isinstance(value, dict):
                        return {str(k).strip(): str(v).strip() for k, v in value.items()}
                except Exception:
                    pass
            values = {}
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip().lower()] = value.strip()
            return values

        def out_dir(name: str):
            d = out / "OUT" / name
            d.mkdir(parents=True, exist_ok=True)
            return d

        def try_pak_unpack(result, target_dir: Path):
            """After decrypt/decompress, try the native PAK parser as well as ZIP."""
            if not isinstance(result, dict) or not result.get("ok"):
                return result
            payload = result.get("out")
            if not payload or not Path(payload).is_file():
                return result
            extract_dir = target_dir / (Path(payload).stem + "_unpacked")
            try:
                unpacked = core.run_pak_unpack(payload, extract_dir)
                if isinstance(unpacked, dict) and unpacked.get("ok"):
                    files = [item for item in extract_dir.rglob("*") if item.is_file()]
                    if files:
                        result["pak_unpack"] = {
                            "ok": True, "files": len(files), "out": str(extract_dir)
                        }
                    else:
                        result["pak_unpack_note"] = "native PAK parser produced no files"
                else:
                    result["pak_unpack_note"] = (
                        unpacked.get("error", "native PAK parser rejected payload")
                        if isinstance(unpacked, dict) else str(unpacked)
                    )
            except Exception as exc:
                result["pak_unpack_note"] = str(exc)[:240]
            return result

        # ── 1  PAK Unpack ────────────────────────────────────────────────
        if mid == 1 or sid.startswith("pak_full") or sid in ("pak_list", "pak_info", "pak_csv"):
            if not need_file(): return "\n".join(lines)
            try:
                raw = Path(ip).read_bytes()
                lines.append("preflight size=%s head=%s" % (len(raw), raw[:8].hex()))
                if len(raw) < 64:
                    lines.append("X File too small for PAK/LuaS")
                    return "\n".join(lines)
                if raw[:4] == b"\x1bLua":
                    lines.append("NOTE: magic LuaS bytecode (NOT a PAK) -> LUA smart")
                    dest = out_dir("LUA")
                    r = feat.run_lua_smart(ip, dest, jars_dir=jars)
                    if r.get("ok"):
                        lines.append("OK mode=%s lines=%s" % (r.get("mode","?"), r.get("lines",0)))
                        lines.append("OUT -> %s" % r.get("out","(see OUT/LUA/)"))
                        if r.get("note"):
                            lines.append("NOTE: %s" % r.get("note"))
                        if r.get("strings_decrypted") is False:
                            lines.append("WARN: bytecode structure was decompiled, but protected string constants were not fully restored")
                        if r.get("vm_obfuscated"):
                            lines.append("NOTE: VM obfuscation detected — decompiled VM interpreter (not original source)")
                    else:
                        lines.append("X OUT -> operation failed")
                    return "\n".join(lines)
                if raw[:2] == b"PK":
                    lines.append("NOTE: ZIP magic — use OBB Tools")
                    return "\n".join(lines)
            except Exception as _e:
                lines.append("preflight-skip: %s" % _e)
            dest = out_dir("PAK") / Path(ip).stem
            dest.mkdir(parents=True, exist_ok=True)
            if sid == "pak_list":
                r = core.run_pak_list(ip, dest / "index_list.txt")
                if not r.get("ok"):
                    lines.append("X PAK LIST FAILED: %s" % r.get("error", r))
                    return "\n".join(lines)
                lines.append("entries=%s -> %s" % (r.get("count"), r.get("out")))
                for pth in (r.get("paths") or [])[:40]:
                    lines.append("  " + pth)
                return "\n".join(lines)
            if sid == "pak_info":
                r = core.run_pak_info(ip, dest / "info.txt")
                if not r.get("ok"):
                    lines.append("X PAK INFO FAILED: %s" % r.get("error", r))
                else:
                    lines.append(r.get("info", str(r)))
                return "\n".join(lines)
            if sid == "pak_csv":
                r = core.run_pak_list(ip, None)
                if not r.get("ok"):
                    lines.append("X PAK CSV FAILED: %s" % r.get("error", r))
                    return "\n".join(lines)
                paths = r.get("paths") or []
                csvp = dest / "index.csv"
                csvp.write_text("path\n" + "\n".join(paths), encoding="utf-8")
                lines.append("OK csv=%s n=%s" % (csvp, len(paths)))
                return "\n".join(lines)
            # Start from a clean destination so stale files can never satisfy
            # the extraction verification below.
            try:
                if dest.exists():
                    shutil.rmtree(dest)
                dest.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                lines.append("X PAK UNPACK FAILED: cannot reset output directory: %s" % (str(exc)[:500]))
                return "\n".join(lines)
            try:
                from archive_engine import extract_archive
                r = extract_archive(ip, dest)
            except Exception as exc:
                lines.append("X PAK UNPACK FAILED: %s" % (str(exc)[:1200] or type(exc).__name__))
                return "\n".join(lines)
            if not isinstance(r, dict) or not r.get("ok"):
                lines.append("X PAK UNPACK FAILED: %s" % (
                    r.get("error", r) if isinstance(r, dict) else str(r)
                ))
                return "\n".join(lines)
            files = [p for p in dest.rglob("*") if p.is_file()]
            lua_files = [p for p in files if p.suffix.lower() == ".lua"]
            if not files:
                lines.append("X PAK UNPACK produced zero files; refusing false success")
                lines.append("Check archive format, index encryption, keys, and core-patch compatibility")
                return "\n".join(lines)
            lines.append("OK PAK UNPACK files=%d lua=%d" % (len(files), len(lua_files)))
            lines.append("OUT -> %s" % dest)
            if not lua_files:
                lines.append("NOTE: no .lua files found in extracted output")
            else:
                names = sorted({p.name for p in lua_files})
                names_by_lower = {name.lower(): name for name in names}
                requested_targets = ("BRPlayerCharacterBase.lua", "CharacterBase.lua")
                found_targets = []
                missing_targets = []
                for target in requested_targets:
                    actual = names_by_lower.get(target.lower())
                    if actual:
                        found_targets.append(actual)
                        lines.append("FOUND TARGET LUA -> %s" % actual)
                    else:
                        missing_targets.append(target)
                if missing_targets:
                    lines.append(
                        "NOTE target filename(s) are not present in this PAK index: %s"
                        % ", ".join(missing_targets)
                    )
                    lines.append(
                        "NOTE: PAK extraction succeeded; target files may be in another PAK or use a different filename."
                    )
                lines.append(
                    "Lua filenames sample -> %s"
                    % ", ".join(names[:12])
                )
            return "\n".join(lines)

        # ── 2  PAK Rebuild ───────────────────────────────────────────────
        if mid == 2 or sid in ("pak_repack_full","pak_inject","pak_encrypt","pak_decrypt_restore"):
            if not need_file(): return "\n".join(lines)
            if sid == "pak_encrypt":
                dest = out_dir("PAK") / (Path(ip).stem + "_enc.pak")
                lines.append(str(core.run_file_simple1_crypt(ip, dest, True)))
                return "\n".join(lines)
            if sid == "pak_decrypt_restore":
                dest = out_dir("PAK") / (Path(ip).stem + "_dec.pak")
                lines.append(str(core.run_file_simple1_crypt(ip, dest, False)))
                return "\n".join(lines)
            pak_file = Path(ip)
            mod_dir = next(
                (c for c in (out/"WORK"/"MOD", out/"OUT"/"PAK"/pak_file.stem,
                             pak_file.parent/"Modified_files") if c.is_dir()),
                None,
            )
            if mod_dir is None:
                lines.append("X Put edited files in OUT/PAK/<stem>/ or WORK/MOD then select base .pak")
                return "\n".join(lines)
            dest = out_dir("PAK") / (pak_file.stem + "_repack.pak")
            from archive_engine import repack_pak
            r = repack_pak(pak_file, mod_dir, dest, smart=True)
            lines.append(str(r))
            return "\n".join(lines)

        # ── 3  PAK Compact ───────────────────────────────────────────────
        if mid == 3 or "delete" in sid:
            if not need_file(): return "\n".join(lines)
            if sid == "pak_delete_all":
                dest = out_dir("PAK") / (Path(ip).stem + "_empty.pak")
                lines.append(str(core.run_pak_delete_all(ip, dest)))
                return "\n".join(lines)
            tfile = out / "WORK" / "delete_targets.txt"
            targets = []
            if tfile.is_file():
                targets = [x.strip() for x in tfile.read_text().splitlines() if x.strip()]
            if not targets:
                lines.append("X Create WORK/delete_targets.txt with one internal path per line")
                return "\n".join(lines)
            dest = out_dir("PAK") / (Path(ip).stem + "_del.pak")
            lines.append(str(core.run_pak_delete_entries(ip, dest, targets)))
            return "\n".join(lines)

        if sid == "obb_integrity_audit":
            if not need_file():
                return "\n".join(lines)
            source = Path(ip)
            target = out_dir("OBB") / (source.name + ".integrity_audit.json")
            try:
                from alvsia_reference_tools import audit_archive_file
                import json as _json
                report = audit_archive_file(source)
                target.write_text(_json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                lines.append("OK archive integrity audit" if report.get("ok") else "WARN archive issues or incomplete CRC coverage")
                lines.append("entries=%s CRC_checked=%s unsafe_paths=%s bad_crc=%s" % (
                    report.get("entries"), report.get("crc_checked_bytes"),
                    len(report.get("unsafe_paths", [])), len(report.get("bad_crc", []))))
                lines.append("OUT -> %s" % target)
                lines.append("Archive was not extracted or modified")
            except Exception as exc:
                lines.append("X OBB integrity audit failed: %s" % str(exc)[:300])
            return "\n".join(lines)

        # ── 4  OBB Tools — unified bounded archive engine ────────────────
        if mid == 4 or sid.startswith("obb_"):
            if not need_file(): return "\n".join(lines)
            from archive_engine import inspect_archive, extract_archive, repack_obb
            p = Path(ip)
            if sid == "obb_info":
                dest = out_dir("OBB") / "info.txt"
                r = inspect_archive(p, dest)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "obb_unzip":
                d = out_dir("OBB") / p.stem
                r = extract_archive(p, d)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "obb_rezip":
                extracted = out_dir("OBB") / p.stem
                if not extracted.is_dir():
                    lines.append("X Extract this OBB first; expected edited tree at OUT/OBB/%s" % p.stem)
                    return "\n".join(lines)
                dest = out_dir("OBB") / (p.stem + "_rezip.obb")
                r = repack_obb(extracted, dest)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 5  LUA Tools ─────────────────────────────────────────────────
        if mid == 5 or sid.startswith("lua_"):
            if sid not in ("lua_decompile",) and not need_file():
                return "\n".join(lines)
            dest_lua = out_dir("LUA")
            if sid == "lua_decompile":
                if not need_file():
                    return "\n".join(lines)
                # One user-facing entry point: Smart Lua owns detection,
                # container normalization, protected-format diagnostics,
                # compatible engine selection and partial recovery.
                result = feat.run_lua_smart(ip, dest_lua, jars_dir=jars)
                if result.get("ok") and result.get("out"):
                    lines.append("OK mode=%s engine=%s" % (
                        result.get("mode", "smart"),
                        result.get("selected_engine", result.get("pattern_id", "auto")),
                    ))
                    lines.append("OUT -> %s" % result.get("out"))
                    if result.get("vm_obfuscated"):
                        lines.append("NOTE: VM protection detected; output type=%s" % (
                            result.get("artifact_kind", "analysis"),
                        ))
                else:
                    lines.append("X No validated Lua source was produced")
                    lines.append("FINAL STATUS: %s" % result.get("final_status", "PARTIAL"))
                    for step in (result.get("steps") or [])[-8:]:
                        detail = step.get("error") or step.get("note") or step.get("format") or ""
                        lines.append("  step=%s ok=%s%s" % (
                            step.get("step"), step.get("ok"),
                            (" detail=" + str(detail)[:220]) if detail else "",
                        ))
                    for key, label in (
                        ("stage_report", "RECOVERY REPORT"),
                        ("structure_out", "STRUCTURE MAP"),
                        ("constants_out", "CONSTANT DUMP"),
                        ("report_out", "RECOVERY REPORT"),
                    ):
                        artifact = result.get(key)
                        if artifact and Path(str(artifact)).is_file():
                            lines.append("OUT %s -> %s" % (label, artifact))
                return "\n".join(lines)
            if sid == "lua_format_probe":
                try:
                    from alvsia_reference_tools import probe_lua_file
                    source = Path(ip)
                    report = probe_lua_file(source)
                    target = dest_lua / (source.stem + "_format_probe.json")
                    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                    lines.append("OK read-only Lua format probe: %s (%s confidence)" % (
                        report.get("format", "unknown"), report.get("confidence", "low")))
                    lines.append("OUT -> %s" % target)
                except Exception as exc:
                    lines.append("X Lua format probe failed: %s" % (str(exc)[:300] or type(exc).__name__))
                return "\n".join(lines)
            if sid == "lua_analyze":
                r = feat.run_lua_analyze(ip, dest_lua)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_constants":
                r = feat.run_lua_constants(ip, dest_lua)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_clean_source":
                r = feat.run_lua_clean(ip, dest_lua)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_xor_crypt":
                r = feat.run_lua_xor(ip, dest_lua, key_hex=None)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_multi_xor":
                r = feat.run_lua_multi_xor(ip, dest_lua)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_vm_deobfuscate":
                # Module 05 / VM Deobfuscate — auto-detect known protection patterns
                # (ALVSEAL3, ALVLUA1, BGMI-VM, ...) and extract what's recoverable.
                try:
                    from lua_engine.vm_deobfuscator import vm_deobfuscate
                    from lua_engine.pattern_registry import list_patterns
                    r = vm_deobfuscate(Path(ip), dest_lua)
                    patterns = list_patterns()
                    lines.append("ALVSIA VM Deobfuscator — %d patterns registered" % len(patterns))
                    for p in patterns:
                        lines.append("  · %-18s %s" % (p["id"], p["label"]))
                    lines.append("")
                    if r.get("ok"):
                        lines.append("OK pattern matched: %s" % r.get("pattern_id", "?"))
                        lines.append("  label: %s" % r.get("pattern_label", ""))
                        lines.append("  mode:  %s" % r.get("mode", ""))
                        if r.get("recovered"):
                            lines.append("OK source recovered -> %s" % r.get("out", ""))
                            lines.append("  recovered size: %d bytes" % r.get("recovered_size", 0))
                            lines.append("  is_lua_source:    %s" % r.get("is_lua_source", False))
                        else:
                            lines.append("NOTE partial recovery only — see output files")
                            for k in ("structure_out", "constants_out", "report_out"):
                                if r.get(k):
                                    lines.append("  -> %s" % r[k])
                            if r.get("note"):
                                lines.append("NOTE %s" % r["note"])
                    else:
                        lines.append("X deobfuscate failed: %s" % r.get("error", "unknown"))
                        if r.get("note"):
                            lines.append("NOTE %s" % r["note"])
                    lines.append("elapsed_ms=%s" % r.get("elapsed_ms", 0))
                    return "\n".join(lines)
                except Exception as exc:
                    lines.append("X VM deobfuscate exception: %s" % (str(exc)[:400] or type(exc).__name__))
                    import traceback as _tb
                    lines.append(_tb.format_exc()[:1200])
                    return "\n".join(lines)

        # ── 6  File Scan ─────────────────────────────────────────────────
        if mid == 6 or sid in ("string_scan", "hash_scan", "metadata_v39_decode"):
            if not need_file(): return "\n".join(lines)
            dest_sc = out_dir("SCAN")
            if sid == "metadata_v39_decode":
                try:
                    from alvsia_metadata import decode_metadata_v39_file
                    source = Path(ip)
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
                    target = dest_sc / (source.stem + "_metadata_decoded_" + digest + ".dat")
                    report = decode_metadata_v39_file(source, target)
                    report_path = target.with_suffix(target.suffix + ".json")
                    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                    lines.append("OK IL2CPP metadata v39 decoded and all section ranges validated")
                    lines.append("sections=%s overlaps=%s" % (report.get("section_count"), len(report.get("overlaps", []))))
                    lines.append("OUT -> %s" % target)
                    lines.append("REPORT -> %s" % report_path)
                    lines.append("Original input preserved; output written atomically")
                except Exception as exc:
                    lines.append("X metadata v39 decode failed: %s" % str(exc)[:500])
                return "\n".join(lines)
            if sid == "string_scan":
                r = feat.run_strings_scan(ip, dest_sc)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "hash_scan":
                # run_hash_file expects an output FILE path (not a directory)
                dest_hash = dest_sc / (Path(ip).stem + "_hash.txt")
                r = feat.run_hash_file(ip, dest_hash)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 7  Workspace ─────────────────────────────────────────────────
        if mid == 7 or sid == "clear_work":
            for d in (out / "WORK", out / "OUT"):
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
                    d.mkdir(parents=True, exist_ok=True)
            lines.append("OK workspace cleared")
            return "\n".join(lines)

        # ── 8  Export Report ─────────────────────────────────────────────
        if mid == 8 or sid == "export_report":
            if not need_file(): return "\n".join(lines)
            r = feat.run_export_report(ip, out_dir("REPORT"))
            lines.append(str(r))
            return "\n".join(lines)

        # ── 9  Rebrand ───────────────────────────────────────────────────
        if mid == 9 or sid.startswith("rebrand_"):
            if not need_file(): return "\n".join(lines)
            cfg_path = str(work_dir() / "rebrand_config.txt")
            if sid == "rebrand_auto":
                r = feat.run_rebrand(ip, out_dir("REBRAND"), cfg_path, auto=True)
            elif sid == "rebrand_manual":
                r = feat.run_rebrand(ip, out_dir("REBRAND"), cfg_path, auto=False)
            elif sid == "rebrand_scan":
                r = feat.run_rebrand_scan(ip, out_dir("REBRAND"))
            else:
                r = {"ok": False, "msg": "unknown rebrand sub"}
            lines.append(str(r))
            return "\n".join(lines)

        # ── 10  SO Analyzer ──────────────────────────────────────────────
        if mid == 10 or sid.startswith("so_"):
            import alvsia_ultimate as ult
            if not need_file(): return "\n".join(lines)
            dest_so = out_dir("SO")
            if sid == "so_dump_audit":
                try:
                    from alvsia_reference_tools import inspect_dump_file
                    source = Path(ip)
                    report = inspect_dump_file(source)
                    target = dest_so / (source.stem + "_offline_dump.json")
                    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                    lines.append("OK offline dump inspection; no live process access or secret extraction")
                    lines.append("size=%s sha256=%s" % (report.get("size"), report.get("sha256")))
                    lines.append("OUT -> %s" % target)
                except Exception as exc:
                    lines.append("X offline dump inspection failed: %s" % (str(exc)[:300] or type(exc).__name__))
                return "\n".join(lines)
            if sid == "so_xor_scan":
                r = ult.so_xor_brute(ip, dest_so)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "so_multi_xor":
                key_file = work_dir() / "xor_keys.txt"
                keys = [ln.strip().replace(" ", "") for ln in key_file.read_text().splitlines()
                        if ln.strip()] if key_file.is_file() else []
                if not keys:
                    lines.append("X Add one hexadecimal XOR key per line to WORK/xor_keys.txt")
                    return "\n".join(lines)
                results = []
                for index, key_hex in enumerate(keys, 1):
                    result = ult.so_multi_xor(ip, dest_so, key_hex)
                    if result.get("ok") and result.get("out"):
                        generated = Path(result["out"])
                        unique = dest_so / ("so_xored_key%02d_%s" % (index, Path(ip).name))
                        try:
                            generated.replace(unique)
                            result["out"] = str(unique)
                        except Exception:
                            pass
                    results.append(result)
                lines.append(str({"ok": any(x.get("ok") for x in results),
                                  "keys_tried": len(keys), "results": results}))
                return "\n".join(lines)
            if sid == "so_url_dump":
                r = ult.so_url_dump(ip, dest_so)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "so_aes_probe":
                r = ult.so_aes_probe(ip, dest_so)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "so_patch_url":
                cfg = read_config("patch_config.txt")
                old_url, new_url = cfg.get("old_url", ""), cfg.get("new_url", "")
                if not old_url or not new_url:
                    lines.append("X WORK/patch_config.txt must contain old_url=<existing URL> and new_url=<replacement URL>")
                    return "\n".join(lines)
                r = ult.so_patch_url(ip, dest_so, old_url, new_url)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 11  Frida Tracer ─────────────────────────────────────────────
        if mid == 11 or sid.startswith("frida_"):
            import alvsia_ultimate as ult
            dest_fr = out_dir("FRIDA")
            pkg_file = work_dir() / "frida_target.txt"
            pkg = pkg_file.read_text().strip() if pkg_file.exists() else ""
            if sid == "frida_js_dump":
                r = ult.frida_generate_script(pkg or "com.example.app", dest_fr)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "frida_jni_hook":
                if not need_file():
                    return "\n".join(lines)
                r = ult.frida_jni_hook(ip, dest_fr)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "frida_spawn":
                if not pkg:
                    lines.append("X Write target package to WORK/frida_target.txt")
                    return "\n".join(lines)
                r = ult.frida_spawn_trace(pkg, dest_fr)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 12  XOR Suite ────────────────────────────────────────────────
        if mid == 12 or sid.startswith("xor_"):
            import alvsia_ultimate as ult
            if sid not in ("xor_batch", "xor_selftest") and not need_file():
                return "\n".join(lines)
            dest_xor = out_dir("XOR")
            if sid == "xor_selftest":
                test_dir = dest_xor / ".selftest_tmp"
                test_dir.mkdir(parents=True, exist_ok=True)
                plain = b"ALVSIA XOR engine self-test v1"
                key_hex = "DEADBEEF"
                expected_cipher_hex = "9fe1e8bc97ec9eb791ff9e8ab0cad781bb8dcd8ab2cb939bbbdecacfa89c"
                report = {"test": "repeating-key XOR known vector", "key_hex": key_hex}
                try:
                    source = test_dir / "known_plain.bin"
                    source.write_bytes(plain)
                    enc = ult.xor_apply_key(str(source), test_dir, key_hex)
                    enc_path = Path(enc.get("out", "")) if isinstance(enc, dict) else Path("")
                    cipher_ok = bool(enc.get("ok")) and enc_path.is_file() and enc_path.read_bytes().hex() == expected_cipher_hex
                    dec = ult.xor_apply_key(str(enc_path), test_dir, key_hex) if cipher_ok else {"ok": False}
                    dec_path = Path(dec.get("out", "")) if isinstance(dec, dict) else Path("")
                    roundtrip_ok = bool(dec.get("ok")) and dec_path.is_file() and dec_path.read_bytes() == plain
                    report.update({"cipher_vector_match": cipher_ok, "roundtrip_match": roundtrip_ok,
                                   "ok": cipher_ok and roundtrip_ok})
                except Exception as exc:
                    report.update({"ok": False, "error": str(exc)[:240]})
                finally:
                    shutil.rmtree(test_dir, ignore_errors=True)
                target = dest_xor / "xor_selftest.json"
                target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                lines.append("OK XOR known-vector self-test" if report.get("ok") else "X XOR self-test failed")
                lines.append("cipher_vector=%s roundtrip=%s" % (
                    report.get("cipher_vector_match"), report.get("roundtrip_match")))
                lines.append("OUT -> %s" % target)
                return "\n".join(lines)
            if sid == "xor_single_byte":
                r = ult.xor_single_byte_scan(ip, dest_xor)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "xor_custom_key":
                kf = work_dir() / "xor_key.txt"
                if not kf.exists():
                    lines.append("X Put key in WORK/xor_key.txt (hex bytes, e.g. DEADBEEF)")
                    return "\n".join(lines)
                key_hex = kf.read_text(encoding="utf-8").strip()
                r = ult.xor_apply_key(ip, dest_xor, key_hex)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "xor_luas_strip":
                r = ult.xor_luas_strip(ip, dest_xor)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "xor_batch":
                batch_dir = work_dir() / "BATCH"
                kf = work_dir() / "xor_key.txt"
                if not kf.exists() or not batch_dir.exists():
                    lines.append("X Need WORK/BATCH/ dir and WORK/xor_key.txt")
                    return "\n".join(lines)
                key_hex = kf.read_text(encoding="utf-8").strip()
                r = ult.xor_batch(str(batch_dir), dest_xor, key_hex)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 13  Decrypt Engine ───────────────────────────────────────────
        if mid == 13 or sid.startswith("dec_"):
            import alvsia_ultimate as ult
            dest_dec = out_dir("DEC")
            if sid == "dec_selftest":
                test_dir = dest_dec / ".selftest_tmp"
                test_dir.mkdir(parents=True, exist_ok=True)
                report = {"test": "NIST AES known-answer tests", "ok": False}
                try:
                    ecb_in = test_dir / "aes_ecb_known.bin"
                    ecb_in.write_bytes(bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a"))
                    ecb = ult.decrypt_aes(str(ecb_in), test_dir / "ecb", "000102030405060708090a0b0c0d0e0f", "")
                    ecb_path = Path(ecb.get("out", "")) if isinstance(ecb, dict) else Path("")
                    ecb_ok = bool(ecb.get("ok")) and ecb_path.is_file() and ecb_path.read_bytes().hex() == "00112233445566778899aabbccddeeff"
                    cbc_in = test_dir / "aes_cbc_known.bin"
                    cbc_in.write_bytes(bytes.fromhex("7649abac8119b246cee98e9b12e9197d"))
                    cbc = ult.decrypt_aes(str(cbc_in), test_dir / "cbc", "2b7e151628aed2a6abf7158809cf4f3c", "000102030405060708090a0b0c0d0e0f")
                    cbc_path = Path(cbc.get("out", "")) if isinstance(cbc, dict) else Path("")
                    cbc_ok = bool(cbc.get("ok")) and cbc_path.is_file() and cbc_path.read_bytes().hex() == "6bc1bee22e409f96e93d7e117393172a"
                    report.update({"aes_ecb_match": ecb_ok, "aes_cbc_match": cbc_ok, "ok": ecb_ok and cbc_ok})
                except Exception as exc:
                    report.update({"error": str(exc)[:240]})
                finally:
                    shutil.rmtree(test_dir, ignore_errors=True)
                target = dest_dec / "decrypt_selftest.json"
                target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                lines.append("OK AES known-answer self-test" if report.get("ok") else "X AES self-test failed")
                lines.append("AES_ECB=%s AES_CBC=%s" % (report.get("aes_ecb_match"), report.get("aes_cbc_match")))
                lines.append("OUT -> %s" % target)
                return "\n".join(lines)
            if not need_file(): return "\n".join(lines)
            if sid == "dec_auto":
                r = ult.decrypt_auto(ip, dest_dec, str(work_dir()))
                lines.append(str(r))
                return "\n".join(lines)
            if sid in ("dec_aes_cbc", "dec_aes_ecb"):
                cfg = read_config("aes_config.txt")
                key_hex = cfg.get("key", cfg.get("key_hex", ""))
                iv_hex = cfg.get("iv", cfg.get("iv_hex", "")) if sid == "dec_aes_cbc" else ""
                if not key_hex or (sid == "dec_aes_cbc" and not iv_hex):
                    lines.append("X WORK/aes_config.txt requires key=<hex>; AES-CBC also requires iv=<hex>")
                    return "\n".join(lines)
                r = ult.decrypt_aes(ip, dest_dec, key_hex, iv_hex)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "dec_zuc":
                cfg = read_config("zuc_config.txt")
                key_hex, iv_hex = cfg.get("key", cfg.get("key_hex", "")), cfg.get("iv", cfg.get("iv_hex", ""))
                if not key_hex:
                    lines.append("X WORK/zuc_config.txt requires key=<hex> (optional iv=<hex>)")
                    return "\n".join(lines)
                r = ult.decrypt_zuc(ip, dest_dec, key_hex, iv_hex)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "dec_sm4":
                cfg = read_config("sm4_config.txt")
                key_hex = cfg.get("key", cfg.get("key_hex", ""))
                mode = cfg.get("mode", "ECB").upper()
                iv_hex = cfg.get("iv", cfg.get("iv_hex", ""))
                if not key_hex:
                    lines.append("X WORK/sm4_config.txt requires key=<32 hex characters>")
                    return "\n".join(lines)
                if mode == "CBC" and not iv_hex:
                    lines.append("X SM4-CBC requires iv=<32 hex characters>")
                    return "\n".join(lines)
                r = ult.decrypt_sm4(ip, dest_dec, key_hex, mode, iv_hex)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "dec_simple1":
                r = ult.decrypt_simple1(ip, dest_dec)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 14  PAK Deep ─────────────────────────────────────────────────
        if sid == "pak_deep_integrity_audit":
            if not need_file():
                return "\n".join(lines)
            dest_pakd = out_dir("PAKD")
            target = dest_pakd / (Path(ip).name + ".integrity_audit.json")
            try:
                result = core.run_pak_integrity_audit(ip, target)
                lines.append("OK range validation complete" if result.get("ok") else "WARN invalid payload/index ranges detected")
                lines.append("entries=%s invalid_ranges=%s overlaps=%s" % (
                    result.get("entry_count"), len(result.get("invalid_ranges", [])),
                    len(result.get("overlaps", []))))
                if result.get("warnings"):
                    lines.append("WARN: %s" % "; ".join(result.get("warnings", [])))
                lines.append("OUT -> %s" % result.get("out", target))
                lines.append("Original PAK was not modified")
            except Exception as exc:
                lines.append("X PAK integrity audit failed: %s" % str(exc)[:300])
            return "\n".join(lines)

        if mid == 14 or sid.startswith("pak_deep_"):
            import alvsia_ultimate as ult
            if not need_file(): return "\n".join(lines)
            dest_pakd = out_dir("PAKD")
            if sid == "pak_deep_aes":
                cfg = read_config("pak_pass.txt")
                key_hex = cfg.get("key", cfg.get("key_hex", ""))
                iv_hex = cfg.get("iv", cfg.get("iv_hex", ""))
                passphrase = cfg.get("passphrase", "")
                if not passphrase and not key_hex:
                    raw_cfg = (work_dir() / "pak_pass.txt")
                    if raw_cfg.is_file():
                        raw_text = raw_cfg.read_text(encoding="utf-8").strip()
                        if raw_text and "=" not in raw_text:
                            passphrase = raw_text
                if not key_hex and passphrase:
                    key_hex = hashlib.sha1(passphrase.encode("utf-8")).hexdigest()[:32]
                if not key_hex or not iv_hex:
                    lines.append("X WORK/pak_pass.txt requires passphrase=<text> plus iv=<32 hex chars>, or key=<32 hex chars> plus iv=<32 hex chars>")
                    return "\n".join(lines)
                r = ult.pak_deep_aes(ip, dest_pakd, key_hex, iv_hex)
                r = try_pak_unpack(r, dest_pakd)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "pak_deep_zstd":
                r = ult.pak_deep_zstd(ip, dest_pakd)
                r = try_pak_unpack(r, dest_pakd)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "pak_deep_zuc":
                cfg = read_config("zuc_config.txt")
                key_hex, iv_hex = cfg.get("key", cfg.get("key_hex", "")), cfg.get("iv", cfg.get("iv_hex", ""))
                if not key_hex:
                    lines.append("X WORK/zuc_config.txt requires key=<hex>")
                    return "\n".join(lines)
                r = ult.pak_deep_zuc(ip, dest_pakd, key_hex, iv_hex)
                r = try_pak_unpack(r, dest_pakd)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "pak_deep_sm4":
                cfg = read_config("sm4_config.txt")
                key_hex = cfg.get("key", cfg.get("key_hex", ""))
                mode = cfg.get("mode", "ECB").upper()
                iv_hex = cfg.get("iv", cfg.get("iv_hex", ""))
                if not key_hex:
                    lines.append("X WORK/sm4_config.txt requires key=<32 hex characters>")
                    return "\n".join(lines)
                if mode == "CBC" and not iv_hex:
                    lines.append("X SM4-CBC requires iv=<32 hex characters>")
                    return "\n".join(lines)
                r = ult.pak_deep_sm4(ip, dest_pakd, key_hex, mode, iv_hex)
                r = try_pak_unpack(r, dest_pakd)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "pak_deep_auto":
                native_dir = dest_pakd / (Path(ip).stem + "_native")
                try:
                    native_result = core.run_pak_unpack(ip, native_dir)
                except Exception as exc:
                    native_result = {"ok": False, "error": str(exc)[:240]}
                native_files = [item for item in native_dir.rglob("*") if item.is_file()] if native_dir.is_dir() else []
                if isinstance(native_result, dict) and native_result.get("ok") and native_files:
                    r = {"ok": True, "method": "native_pak_parser",
                         "files": len(native_files), "out": str(native_dir)}
                else:
                    r = ult.pak_deep_auto(ip, dest_pakd)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 15  String Recover ───────────────────────────────────────────
        if mid == 15 or sid.startswith("str_"):
            import alvsia_ultimate as ult
            if not need_file(): return "\n".join(lines)
            dest_str = out_dir("STR")
            if sid == "str_recover":
                r = ult.string_recover(ip, dest_str)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "str_constant_pool":
                r = ult.string_constant_pool(ip, dest_str)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "str_xref":
                cfg = read_config("xref_query.txt")
                query = cfg.get("search", cfg.get("query", ""))
                if not query:
                    lines.append("X Enter search=<text> in WORK/xref_query.txt")
                    return "\n".join(lines)
                r = ult.string_xref(ip, dest_str, query)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 16  Lua Inject ───────────────────────────────────────────────
        if mid == 16 or sid.startswith("lua_patch_") or sid in ("lua_inject_hook","lua_mod_repack"):
            import alvsia_ultimate as ult
            if not need_file(): return "\n".join(lines)
            dest_inj = out_dir("LINJ")
            wdir = str(work_dir())
            if sid == "lua_patch_byte":
                cfg = read_config("lua_patch.json")
                patch_offset = cfg.get("offset", "")
                patch_hex = cfg.get("patch_hex", cfg.get("bytes", ""))
                if not patch_offset or not patch_hex:
                    lines.append("X WORK/lua_patch.json must contain offset=0x1234 and patch_hex=DEADBEEF")
                    return "\n".join(lines)
                r = ult.lua_patch_bytecode(ip, dest_inj, patch_offset, patch_hex)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_inject_hook":
                hf = work_dir() / "lua_hook.lua"
                if not hf.is_file():
                    lines.append("X Enter hook Lua source in the CONFIG field (saved as WORK/lua_hook.lua)")
                    return "\n".join(lines)
                r = ult.lua_inject_hook(ip, dest_inj, str(hf))
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "lua_mod_repack":
                pak_file = Path(ip)
                mod_dir = next((candidate for candidate in (
                    work_dir() / "MOD", out / "OUT" / "PAK" / pak_file.stem,
                    pak_file.parent / "Modified_files"
                ) if candidate.is_dir()), None)
                if mod_dir is None:
                    lines.append("X Add the modified tree to WORK/MOD or OUT/PAK/<pak-name> before repacking")
                    return "\n".join(lines)
                dest = dest_inj / (pak_file.stem + "_modded.pak")
                result = core.run_pak_smart_repack(pak_file, mod_dir, dest)
                if not result.get("ok"):
                    result = core.run_pak_repack(pak_file, mod_dir, dest)
                lines.append(str(result))
                return "\n".join(lines)

        # ── 17  Anti-RE Audit ────────────────────────────────────────────
        if mid == 17 or sid.startswith("audit_") or sid == "anti_re_source_triage":
            import alvsia_ultimate as ult
            if not need_file(): return "\n".join(lines)
            dest_audit = out_dir("AUDIT")
            if sid == "anti_re_source_triage":
                try:
                    from alvsia_reference_tools import scan_source_file
                    source = Path(ip)
                    report = scan_source_file(source)
                    target = dest_audit / (source.stem + "_source_triage.json")
                    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                    lines.append("OK static-only source triage; input was not executed or modified")
                    lines.append("indicators=%s sha256=%s" % (
                        len(report.get("findings", [])), report.get("sha256")))
                    lines.append("OUT -> %s" % target)
                except Exception as exc:
                    lines.append("X source triage failed: %s" % (str(exc)[:300] or type(exc).__name__))
                return "\n".join(lines)
            if sid == "audit_apk":
                r = ult.audit_apk(ip, dest_audit)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "audit_lua":
                r = ult.audit_lua(ip, dest_audit)
                lines.append(str(r))
                return "\n".join(lines)
            if sid == "audit_so":
                r = ult.audit_so(ip, dest_audit)
                lines.append(str(r))
                return "\n".join(lines)

        # ── 18  Lua Protector (authenticated encrypted package) ───────────
        if mid == 18 or sid in ("lua_protect_encrypt", "lua_protect_decrypt",
                                 "lua_vm_protect"):
            if not need_file():
                return "\n".join(lines)
            dest_dir = out_dir("LPROTECT")

            # ── 18 / VM-protect: BGMI-style self-executing Lua source ────
            if sid == "lua_vm_protect":
                try:
                    from alvsia_vm_protect import vm_protect
                    dest = dest_dir / (Path(ip).stem + ".alvlua3.lua")
                    r = vm_protect(Path(ip), dest, output_format="lua",
                                    num_decoys=1024)
                    if r.get("ok"):
                        lines.append("OK VM-protected Lua payload (BGMI pattern)")
                        lines.append("mode=%s payload=%d bytes decoys=%d" % (
                            r.get("mode"), r.get("payload_size", 0),
                            r.get("decoys", 0)))
                        lines.append("OUT -> %s" % r.get("out"))
                        lines.append("NOTE: self-executing — load() runs the original code")
                        lines.append("NOTE: reversible via module 05 / VM Deobfuscate")
                    else:
                        lines.append("X VM protect failed: %s" % r.get("error"))
                    return "\n".join(lines)
                except Exception as exc:
                    lines.append("X VM protect exception: %s" % (str(exc)[:400] or type(exc).__name__))
                    return "\n".join(lines)

            # ── 18 / AES-GCM encrypt + decrypt (original ALVLUA1 format) ──
            try:
                from Crypto.Cipher import AES
                from Crypto.Random import get_random_bytes
                key_file = work_dir() / "lua_protect_key.txt"
                if not key_file.is_file():
                    lines.append("X Create WORK/lua_protect_key.txt with a 64-character hex key (32 random bytes)")
                    return "\n".join(lines)
                key_hex = key_file.read_text(encoding="utf-8").strip()
                if not re.fullmatch(r"[0-9a-fA-F]{64}", key_hex):
                    lines.append("X Lua Protector key must be exactly 64 hexadecimal characters")
                    return "\n".join(lines)
                key = bytes.fromhex(key_hex)
                source = Path(ip).read_bytes()
                dest_dir = out_dir("LPROTECT")
                if sid == "lua_protect_encrypt":
                    nonce = get_random_bytes(12)
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
                    cipher.update(b"ALVLUA1")
                    ciphertext, tag = cipher.encrypt_and_digest(source)
                    dest = dest_dir / (Path(ip).stem + ".alvlua")
                    dest.write_bytes(b"ALVLUA1" + nonce + tag + ciphertext)
                    lines.append("OK encrypted + authenticated Lua payload")
                    lines.append("NOTE keep the 32-byte key private; it is not embedded in the output")
                elif sid == "lua_protect_decrypt":
                    if len(source) < 35 or source[:7] != b"ALVLUA1":
                        lines.append("X Invalid ALVLUA1 header or truncated payload")
                        return "\n".join(lines)
                    nonce, tag, ciphertext = source[7:19], source[19:35], source[35:]
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
                    cipher.update(b"ALVLUA1")
                    try:
                        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                    except ValueError:
                        lines.append("X Authentication failed: wrong key or modified payload")
                        return "\n".join(lines)
                    dest = dest_dir / (Path(ip).stem + ".lua")
                    dest.write_bytes(plaintext)
                    lines.append("OK authentication passed; Lua source restored")
                else:
                    lines.append("X Unknown Lua Protector operation")
                    return "\n".join(lines)
                lines.append("OUT -> %s" % dest)
                return "\n".join(lines)
            except ImportError:
                lines.append("X PyCryptodome AES module unavailable in this runtime")
                return "\n".join(lines)
            except Exception as exc:
                lines.append("X Lua Protector failed: %s" % (str(exc)[:400] or type(exc).__name__))
                return "\n".join(lines)

        # ── SM4 Key Finder (sub_id: "sm4_keyfind") ───────────────────────
        # Scans a folder of .so files extracted from an APK/OBB for embedded
        # SM4_SECRET_NEW candidates — the 20-char aA0-pattern keys used by
        # BGMI-style PAK encryption.  Input: folder path (not a single file).
        elif sid == "sm4_keyfind":
            from alvsia_features import SM4KeyFinder
            so_dir = Path(ip) if ip and Path(ip).is_dir() else None
            if so_dir is None:
                # Treat input as a single .so file — scan its parent folder.
                so_dir = Path(ip).parent if ip and Path(ip).is_file() else None
            if so_dir is None:
                lines.append("X input must be a folder containing .so files or a .so file path")
                return "\n".join(lines)
            try:
                finder = SM4KeyFinder(str(so_dir))
                hits = finder.find_keys()
                if not hits:
                    lines.append("No SM4_SECRET_NEW candidates found in %s" % so_dir)
                else:
                    lines.append("Found %d candidate(s) in %s:" % (len(hits), so_dir))
                    for offset, key in hits:
                        lines.append("  0x%08X  %s" % (offset, key))
                    # Write result file
                    result_file = out_dir("SM4") / "sm4_keys.txt"
                    result_file.write_text("\n".join(k for _, k in hits))
                    lines.append("OUT -> %s" % result_file)
            except Exception as exc:
                lines.append("X SM4KeyFinder error: %s" % str(exc)[:300])
            return "\n".join(lines)



        # ══════════════════════════════════════════════════════════════════════
        # ALVSIA PRIVATE TOOL — sealed runtime required for all sub-ids below
        # ══════════════════════════════════════════════════════════════════════
        elif sid in (
            "priv_zuc_decrypt",    "priv_aes_scan",      "priv_xor_recover",
            "priv_lua_parse",      "priv_lua_convert",   "priv_lua_heping",
            "priv_compress_fit",   "priv_apk_audit",     "priv_str_recover",
            "priv_entropy_map",    "priv_pak_manifest",  "priv_apk_manifest",
            "priv_lua_probe",      "priv_source_triage", "priv_dump_audit",
        ):
            # Gate: sealed runtime must be active
            import os as _ose
            if _ose.environ.get("ALVSIA_SEALED_RUNTIME") != "1":
                lines.append("X ALVSIA PRIVATE TOOL: sealed runtime not active")
                lines.append("X Authenticate via ALVSIA panel first")
                return "\n".join(lines)
            # New read-only reference inspectors. Inputs are never executed and
            # process memory is never acquired by these subtools.
            if sid in ("priv_lua_probe", "priv_source_triage", "priv_dump_audit"):
                if not need_file():
                    return "\n".join(lines)
                from alvsia_reference_tools import (
                    probe_lua_file, scan_source_file, inspect_dump_file
                )
                import json as _json
                source_path = Path(ip)
                if not source_path.is_file():
                    lines.append("X This inspector accepts one file at a time")
                    return "\n".join(lines)
                if sid == "priv_lua_probe":
                    report = probe_lua_file(source_path)
                    out_file = out_dir("REFERENCE") / (source_path.name + ".lua_probe.json")
                elif sid == "priv_source_triage":
                    report = scan_source_file(source_path)
                    out_file = out_dir("REFERENCE") / (source_path.name + ".source_triage.json")
                else:
                    report = inspect_dump_file(source_path)
                    out_file = out_dir("REFERENCE") / (source_path.name + ".dump_audit.json")
                out_file.write_text(_json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
                lines.append("OK read-only inspection complete")
                lines.append("OUT -> %s" % out_file)
                if sid == "priv_lua_probe":
                    lines.append("format=%s confidence=%s" % (report.get("format"), report.get("confidence")))
                elif sid == "priv_source_triage":
                    lines.append("indicators=%s (static only; no execution)" % len(report.get("findings", [])))
                else:
                    lines.append("blocks=%s strings=%s (offline file only)" % (
                        len(report.get("blocks", [])), len(report.get("strings", []))))
                return "\n".join(lines)

            from alvsia_private import (
                ZUCCipher, AESKeyScanner, XORKeyRecovery, LuaBytecodeParser,
                LuaOpcodeConverter, CompressionBestFit, APKAuditor,
                StringConstantRecovery, EntropyAnalyzer, PAKManifestGenerator,
                AlvsiaLuaWriter,
            )
            dest = out_dir("ALVSIA_PRIVATE")

            # ── ZUC-128 decrypt ──────────────────────────────────────────────
            if sid == "priv_zuc_decrypt":
                if not need_file(): return "\n".join(lines)
                cfg = read_config("zuc_config.txt")
                key_hex = cfg.get("key", "")
                iv_hex  = cfg.get("iv", "")
                if len(key_hex) != 32 or len(iv_hex) != 32:
                    lines.append("X ZUC key and IV must each be 32 hex chars (16 bytes)")
                    return "\n".join(lines)
                try:
                    data_in = Path(ip).read_bytes()
                    zuc = ZUCCipher(bytes.fromhex(key_hex), bytes.fromhex(iv_hex))
                    out_file = dest / (Path(ip).stem + "_zuc_dec.bin")
                    out_file.write_bytes(zuc.decrypt(data_in))
                    lines.append("ZUC decrypt: %d bytes" % len(data_in))
                    lines.append("OUT -> %s" % out_file)
                except Exception as e:
                    lines.append("X ZUC error: %s" % str(e)[:200])

            # ── AES key scanner ──────────────────────────────────────────────
            elif sid == "priv_aes_scan":
                if not need_file(): return "\n".join(lines)
                hits = AESKeyScanner.scan_file(ip)
                if not hits:
                    lines.append("No AES key material found in %s" % ip)
                else:
                    lines.append("Found %d AES indicators:" % len(hits))
                    out_lines = []
                    for h in hits:
                        line = "[%s] %s  key=%s" % (
                            h["type"], h["offset"], h.get("raw_key", "-"))
                        lines.append("  " + line)
                        out_lines.append(line)
                    r = dest / "aes_scan.txt"
                    r.write_text("\n".join(out_lines))
                    lines.append("OUT -> %s" % r)

            # ── XOR key recovery ─────────────────────────────────────────────
            elif sid == "priv_xor_recover":
                if not need_file(): return "\n".join(lines)
                data_in = Path(ip).read_bytes()
                results = XORKeyRecovery.recover(data_in, max_key_len=32)
                if not results:
                    lines.append("No XOR key candidates found")
                else:
                    lines.append("Top XOR key candidates:")
                    out_lines = []
                    for kl, key_b, score in results[:5]:
                        line = "key_len=%d  key=%s  score=%.3f" % (kl, key_b.hex(), score)
                        lines.append("  " + line)
                        out_lines.append(line)
                    r = dest / "xor_keys.txt"
                    r.write_text("\n".join(out_lines))
                    lines.append("OUT -> %s" % r)

            # ── Lua bytecode parser ──────────────────────────────────────────
            elif sid == "priv_lua_parse":
                if not need_file(): return "\n".join(lines)
                data_in = Path(ip).read_bytes()
                try:
                    parser = LuaBytecodeParser(data_in)
                    info   = parser.parse()
                    lines.append("Source  : %s" % info.source_name)
                    lines.append("Lines   : %d–%d" % (info.line_defined, info.last_line))
                    lines.append("Strings : %d  Numbers: %d  Protos: %d" % (
                        len(info.strings), len(info.numbers), info.n_protos))
                    out_lines = ["source: " + info.source_name]
                    for s in info.strings: out_lines.append("str: " + s.value[:120])
                    for n in info.numbers: out_lines.append("num: %s" % n.value)
                    r = dest / (Path(ip).stem + "_parsed.txt")
                    r.write_text("\n".join(out_lines))
                    lines.append("OUT -> %s" % r)
                except Exception as e:
                    lines.append("X Parse error: %s" % str(e)[:200])

            # ── Lua BGMI opcode converter ────────────────────────────────────
            elif sid == "priv_lua_convert":
                if not ip or not (Path(ip).is_file() or Path(ip).is_dir()):
                    lines.append("X input must be a Lua bytecode file or a folder")
                    return "\n".join(lines)
                target = dest / "bgmi_std"
                conv = LuaOpcodeConverter(variant="bgmi")
                if Path(ip).is_dir():
                    report = conv.convert_folder(ip, str(target))
                    ok = sum(1 for v in report.values() if v == "OK")
                    lines.append("BGMI→Std: %d/%d converted" % (ok, len(report)))
                else:
                    if not need_file(): return "\n".join(lines)
                    out_f = target / (Path(ip).stem + "_std.luac")
                    target.mkdir(parents=True, exist_ok=True)
                    conv.convert_file(ip, str(out_f))
                    lines.append("OUT -> %s" % out_f)

            # ── Lua HePing opcode converter ──────────────────────────────────
            elif sid == "priv_lua_heping":
                if not ip or not (Path(ip).is_file() or Path(ip).is_dir()):
                    lines.append("X input must be a Lua bytecode file or a folder")
                    return "\n".join(lines)
                target = dest / "heping_std"
                conv = LuaOpcodeConverter(variant="heping")
                if Path(ip).is_dir():
                    report = conv.convert_folder(ip, str(target))
                    ok = sum(1 for v in report.values() if v == "OK")
                    lines.append("HePing→Std: %d/%d converted" % (ok, len(report)))
                else:
                    if not need_file(): return "\n".join(lines)
                    out_f = target / (Path(ip).stem + "_std.luac")
                    target.mkdir(parents=True, exist_ok=True)
                    conv.convert_file(ip, str(out_f))
                    lines.append("OUT -> %s" % out_f)

            # ── Compression best-fit ─────────────────────────────────────────
            elif sid == "priv_compress_fit":
                if not need_file(): return "\n".join(lines)
                cfg = read_config("compress_config.txt")
                method = cfg.get("method", "zlib")
                try:
                    target_sz = int(cfg.get("target_size", "0"))
                except ValueError:
                    target_sz = 0
                data_in = Path(ip).read_bytes()
                result = CompressionBestFit.compress(data_in, method=method,
                                                     target_size=target_sz)
                if result:
                    out_f = dest / (Path(ip).stem + "_compressed.bin")
                    out_f.write_bytes(result)
                    if data_in:
                        ratio = len(result) / len(data_in) * 100
                        lines.append("%s compress: %d→%d bytes (%.1f%%)" % (
                            method, len(data_in), len(result), ratio))
                    else:
                        lines.append("%s compress: 0→%d bytes (empty input)" % (
                            method, len(result)))
                    lines.append("OUT -> %s" % out_f)
                else:
                    lines.append("X Compression failed — no level fits target size %d" % target_sz)

            # ── APK auditor ──────────────────────────────────────────────────
            elif sid == "priv_apk_audit":
                target_file = ip if ip and Path(ip).suffix.lower() == ".apk" else None
                if not target_file or not Path(target_file).is_file():
                    lines.append("X input must be an .apk file")
                    return "\n".join(lines)
                summary = APKAuditor.audit_file(target_file)
                for l in summary.split("\n"): lines.append(l)
                r = dest / "apk_audit.txt"
                r.write_text(summary)
                lines.append("OUT -> %s" % r)

            # ── APK manifest extract ─────────────────────────────────────────
            elif sid == "priv_apk_manifest":
                if not need_file(): return "\n".join(lines)
                try:
                    import zipfile as _zf
                    with _zf.ZipFile(ip, "r") as zf:
                        raw_manifest = zf.read("AndroidManifest.xml")
                    r = dest / "AndroidManifest.raw.xml"
                    r.write_bytes(raw_manifest)
                    lines.append("Manifest extracted: %d bytes" % len(raw_manifest))
                    pkg = APKAuditor._find_package(raw_manifest)
                    lines.append("Package (best-effort): %s" % pkg)
                    lines.append("OUT -> %s" % r)
                except Exception as e:
                    lines.append("X Manifest extract error: %s" % str(e)[:200])

            # ── String constant recovery ──────────────────────────────────────
            elif sid == "priv_str_recover":
                if not need_file(): return "\n".join(lines)
                data_in = Path(ip).read_bytes()
                results = StringConstantRecovery.recover(data_in)
                out_lines = []
                for r_item in results[:5]:
                    lines.append("[%s] key=%s score=%.3f  %d strings" % (
                        r_item["method"], r_item["key"][:16] or "none",
                        r_item["score"], len(r_item["strings"])))
                    out_lines.append("## method=%s key=%s" % (
                        r_item["method"], r_item["key"][:32]))
                    out_lines.extend(r_item["strings"][:30])
                r = dest / "strings_recovered.txt"
                r.write_text("\n".join(out_lines))
                lines.append("OUT -> %s" % r)

            # ── Entropy map ───────────────────────────────────────────────────
            elif sid == "priv_entropy_map":
                if not need_file(): return "\n".join(lines)
                summary = EntropyAnalyzer.analyze_file(ip)
                out_lines = [
                    "ALVSIA Entropy Analysis",
                    "Total blocks   : %d" % summary["total_blocks"],
                    "Mean entropy   : %.3f" % summary["overall_mean"],
                    "High (enc/comp): %d blocks" % len(summary["high_entropy"]),
                    "Low (padding)  : %d blocks" % len(summary["low_entropy"]),
                    "Code-like      : %d blocks" % len(summary["code_like"]),
                    "",
                    "High-entropy offsets (top 20):",
                ]
                for off, h in summary["high_entropy"][:20]:
                    out_lines.append("  0x%08X  H=%.3f" % (off, h))
                r = dest / "entropy_map.txt"
                r.write_text("\n".join(out_lines))
                for l in out_lines[:8]: lines.append(l)
                lines.append("OUT -> %s" % r)

            # ── PAK manifest ──────────────────────────────────────────────────
            elif sid == "priv_pak_manifest":
                if not need_file(): return "\n".join(lines)
                gen = PAKManifestGenerator(ip)
                csv = gen.generate()
                r = dest / (Path(ip).stem + "_manifest.csv")
                r.write_text(csv)
                n = csv.count("\n")
                lines.append("Manifest: %d entries" % n)
                lines.append("OUT -> %s" % r)

            return "\n".join(lines)

        # ── SM4 All-Type Key Finder ──────────────────────────────────────────
        elif sid == "sm4_find_all":
            from alvsia_features import SM4AllKeyFinder
            from pathlib import Path as _P
            so_dir = _P(ip) if ip and _P(ip).is_dir() else (
                _P(ip).parent if ip and _P(ip).is_file() else None)
            if so_dir is None:
                lines.append("X input must be a folder containing .so files or a .so path")
                return "\n".join(lines)
            try:
                finder = SM4AllKeyFinder(str(so_dir))
                hits = finder.find_all_keys()
                total = sum(len(v) for v in hits.values())
                if total == 0:
                    lines.append("No SM4 candidates found in %s" % so_dir)
                else:
                    lines.append("Found %d total candidates in %s:" % (total, so_dir))
                    result_lines = []
                    for key_type in ('SM4_SECRET_NEW', 'SM4_SECRET_4', 'SM4_SECRET_2'):
                        for off, key in hits[key_type]:
                            lines.append("  [%s] 0x%08X  %s" % (key_type, off, key))
                            result_lines.append("%s  %s" % (key_type, key))
                    dest = out_dir("SM4") / "sm4_all_keys.txt"
                    dest.write_text("\n".join(result_lines))
                    lines.append("OUT -> %s" % dest)
            except Exception as exc:
                lines.append("X SM4AllKeyFinder error: %s" % str(exc)[:300])
            return "\n".join(lines)

        # ── URL Scanner for .so / APK binaries ──────────────────────────────
        elif sid == "url_scan_so":
            from alvsia_features import BinaryURLScanner
            from pathlib import Path as _P
            if not ip or not (_P(ip).is_file() or _P(ip).is_dir()):
                lines.append("X input must be a .so file or folder")
                return "\n".join(lines)
            try:
                scanner = BinaryURLScanner()
                if _P(ip).is_file():
                    hits = scanner.scan_file(ip)
                    label = _P(ip).name
                    all_hits = {label: hits} if hits else {}
                else:
                    all_hits = scanner.scan_folder(ip)
                if not all_hits:
                    lines.append("No URLs found in %s" % ip)
                else:
                    dest = out_dir("URLSCAN") / "urls_found.txt"
                    out_lines = []
                    for fname, file_hits in all_hits.items():
                        lines.append("[%s] %d results:" % (fname, len(file_hits)))
                        for kind, val in file_hits[:20]:
                            lines.append("  [%s] %s" % (kind, val[:120]))
                        for kind, val in file_hits:
                            out_lines.append("%s\t%s\t%s" % (fname, kind, val))
                    dest.write_text("\n".join(out_lines))
                    lines.append("OUT -> %s" % dest)
            except Exception as exc:
                lines.append("X BinaryURLScanner error: %s" % str(exc)[:300])
            return "\n".join(lines)

        # ── PUBG/BGMI Lua Bytecode Converter ────────────────────────────────
        elif sid == "pubg_lua_convert":
            from alvsia_features import PUBGLuaConverter
            from pathlib import Path as _P
            if not need_file(): return "\n".join(lines)
            try:
                converter = PUBGLuaConverter()
                dest_dir  = out_dir("PUBGLUA")
                if _P(ip).is_dir():
                    report = converter.convert_folder(ip, str(dest_dir))
                    ok  = sum(1 for v in report.values() if v == 'OK')
                    bad = sum(1 for v in report.values() if v.startswith('FAIL'))
                    lines.append("Converted %d/%d files. %d failed." % (ok, ok+bad, bad))
                    for fn, status in report.items():
                        lines.append("  %s: %s" % (fn, status))
                else:
                    out_file = dest_dir / (_P(ip).stem + "_std.luac")
                    converter.convert_file(ip, str(out_file))
                    lines.append("OUT -> %s" % out_file)
            except Exception as exc:
                lines.append("X PUBGLuaConverter error: %s" % str(exc)[:300])
            return "\n".join(lines)

        # ── T24 Lua v4 bytecode normalizer + validated ALVSIA decompiler ──
        elif sid == "t24_lua_decompile":
            from lua_engine.t24 import convert_t24_file
            from pathlib import Path as _P
            if not need_file():
                return "\n".join(lines)
            source_path = _P(ip)
            if not source_path.is_file():
                lines.append("X T24 decompiler accepts one bytecode file at a time")
                return "\n".join(lines)
            try:
                dest_dir = out_dir("LUA_T24")
                normalized_path = dest_dir / (source_path.stem + "_standard.luac")
                # T24 v4 and the existing PUBG/BGMI normalizer share the
                # project XOR key. Input is never executed or overwritten.
                key = bytes(feat.PUBG_XOR_KEY)
                report = convert_t24_file(source_path, normalized_path, key)
                lines.append("OK T24 bytecode normalized")
                lines.append("instructions=%s prototypes=%s strings=%s" % (
                    report.get("instructions"), report.get("prototypes"), report.get("strings")))
                lines.append("OUT -> %s" % normalized_path)
                decompile_dir = dest_dir / "DECOMPILED"
                result = feat.run_lua_smart(normalized_path, decompile_dir, jars)
                lines.append("DECOMPILE -> %s" % json.dumps(result, ensure_ascii=False, sort_keys=True))
            except Exception as exc:
                lines.append("X T24 Lua error: %s" % str(exc)[:300])
            return "\n".join(lines)

        # ── fallback ─────────────────────────────────────────────────────
        lines.append("X Unknown sub_id='%s' for module=%s" % (sid, mid))
        return "\n".join(lines)

    except Exception as exc:
        lines.append("X BRIDGE EXCEPTION: %s" % exc)
        lines.append(traceback.format_exc())
        return "\n".join(lines)


def bridge_run_sub(module_id, sub_id, input_path, extra_name, work_dir_path, jars_dir_path):
    """Entry point called by PythonBridgeRunner.runBridge() via reflection."""
    return run_tool(
        module_id=int(module_id),
        sub_id=str(sub_id),
        input_path=str(input_path) if input_path else "",
        out_root=str(work_dir_path),
        engine_dir=str(jars_dir_path),
        jars_dir=str(jars_dir_path),
    )

# ── SM4 All-Type Key Finder (sub_id: "sm4_find_all") ─────────────────────────
# Detects SM4_SECRET_NEW + SM4_SECRET_4 + SM4_SECRET_2 from .so files
