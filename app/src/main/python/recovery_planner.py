"""ALVSIA recovery planner.

Deterministic orchestration metadata shared by Smart engines. It never executes
unknown recovered code and never upgrades a partial artifact to SUCCESS.
The planner turns observed evidence into explicit next actions so callers can
continue recovery instead of treating the first failed provider as terminal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_recovery_plan(result: dict[str, Any], *, domain: str = "generic") -> dict[str, Any]:
    status = str(result.get("final_status") or ("SUCCESS" if result.get("ok") else "FAILED")).upper()
    artifact_kind = str(result.get("artifact_kind") or "").lower()
    source_recovered = bool(result.get("source_recovered"))
    strings_recovered = bool(result.get("strings_recovered"))
    actions: list[dict[str, Any]] = []

    if status in {"SUCCESS", "STRUCTURALLY_VALID"} and source_recovered:
        actions.append({"action": "validate_roundtrip", "priority": 1,
                        "reason": "validated source candidate exists"})
        actions.append({"action": "compare_candidates", "priority": 2,
                        "reason": "look for independent agreement before promotion"})
    elif status == "PARTIAL_STRING_RECOVERY" or artifact_kind == "string_recovery" or strings_recovered:
        actions.extend([
            {"action": "classify_dialect", "priority": 1,
             "reason": "strings alone do not prove source reconstruction"},
            {"action": "recover_constants_and_references", "priority": 2,
             "reason": "associate strings with bytecode offsets/functions"},
            {"action": "reconstruct_ir", "priority": 3,
             "reason": "lift recoverable instructions into a neutral representation"},
            {"action": "reconstruct_source_candidate", "priority": 4,
             "reason": "generate source only from validated structural evidence"},
            {"action": "semantic_roundtrip_validation", "priority": 5,
             "reason": "reject syntactically valid but semantically wrong candidates"},
        ])
    elif status == "PARTIAL":
        actions.extend([
            {"action": "inspect_protection_layers", "priority": 1,
             "reason": "partial recovery indicates additional transformation layers"},
            {"action": "try_compatible_backend", "priority": 2,
             "reason": "another format-specific engine may still accept the payload"},
            {"action": "reconstruct_ir", "priority": 3,
             "reason": "preserve recoverable structure even when source emission fails"},
            {"action": "validate_candidate", "priority": 4,
             "reason": "candidate must be structurally and semantically checked"},
        ])
    else:
        actions.extend([
            {"action": "deep_detect", "priority": 1,
             "reason": "format/dialect is not sufficiently established"},
            {"action": "try_protection_adapters", "priority": 2,
             "reason": "unknown wrappers may hide a supported payload"},
            {"action": "bounded_fallback_recovery", "priority": 3,
             "reason": "collect evidence without fabricating source"},
        ])

    pipeline = [
        {"stage": "observe", "state": "complete", "evidence": ["status", "artifact_kind"]},
        {"stage": "route", "state": "complete", "evidence": ["domain", "actions"]},
        {"stage": "lift_ir", "state": "pending" if status != "FAILED" else "blocked",
         "evidence": ["instruction_boundaries", "constants", "references"]},
        {"stage": "cfg_ssa", "state": "pending" if status != "FAILED" else "blocked",
         "evidence": ["control_flow", "data_flow"]},
        {"stage": "reconstruct", "state": "pending" if status != "FAILED" else "blocked",
         "evidence": ["validated_ir"]},
        {"stage": "validate", "state": "pending" if status != "FAILED" else "blocked",
         "evidence": ["syntax", "roundtrip", "semantic_agreement"]},
        {"stage": "promote", "state": "pending" if status != "FAILED" else "blocked",
         "evidence": ["best_verified_candidate"]},
    ]

    return {
        "planner": "ALVSIA_RECOVERY_PLANNER",
        "domain": domain,
        "status": status,
        "artifact_kind": artifact_kind or None,
        "source_recovered": source_recovered,
        "strings_recovered": strings_recovered,
        "terminal": status == "FAILED" and not actions,
        "actions": sorted(actions, key=lambda item: (item["priority"], item["action"])),
        "pipeline": pipeline,
        "policy": "evidence-driven; never synthesize unvalidated source",
    }


__all__ = ["build_recovery_plan"]
