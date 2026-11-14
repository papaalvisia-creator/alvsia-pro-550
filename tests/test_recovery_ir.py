from recovery_ir import build_cfg, lift_to_ir, normalize_instructions, rank_candidates


def test_normalize_instructions_rejects_malformed_records():
    rows = normalize_instructions([
        {"pc": 3, "opcode": "LOADK", "operands": [1, 2]},
        {"pc": -1, "opcode": "BAD"},
        {"pc": "x", "opcode": "BAD"},
        {"pc": 1, "opcode": " MOVE "},
    ])
    assert [row.pc for row in rows] == [1, 3]
    assert rows[1].opcode == "LOADK"


def test_cfg_uses_only_known_branch_targets_and_fallthrough():
    ir = lift_to_ir(
        [
            {"pc": 0, "opcode": "LOADK"},
            {"pc": 1, "opcode": "JMP"},
            {"pc": 2, "opcode": "RETURN"},
            {"pc": 5, "opcode": "RETURN"},
        ],
        domain="lua",
        branch_targets={1: [5, 999]},
    )
    assert ir.domain == "lua"
    assert len(ir.blocks) == 3
    assert ir.blocks[1].successors == [2]


def test_candidate_ranking_is_deterministic_and_evidence_only():
    ranked = rank_candidates([
        {"name": "strings", "constant_coverage": 1.0},
        {"name": "source", "source_valid": True, "roundtrip_valid": True,
         "cfg_valid": True, "instruction_coverage": 0.9,
         "constant_coverage": 0.8, "independent_agreement": True},
    ])
    assert ranked[0]["name"] == "source"
    assert ranked[0]["score"] > ranked[1]["score"]
    assert ranked[0]["rank"] == 1


def test_lua53_bytecode_lifts_to_shared_ir(tmp_path):
    import struct
    from recovery_ir import analyze_lua_bytecode
    # Minimal valid Lua 5.3 chunk with one RETURN instruction and no debug data.
    header = (
        b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
        + bytes([4, 8, 4, 8, 8])
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
        + bytes([0])
    )
    proto = (
        bytes([0]) + struct.pack("<iiBBB", 0, 0, 0, 0, 2)
        + struct.pack("<iI", 1, 0x01000026)
        + struct.pack("<i", 0) + struct.pack("<i", 0)
        + struct.pack("<i", 1) + bytes([0]) + struct.pack("<i", 0)
        + struct.pack("<i", 0) + struct.pack("<i", 0)
    )
    path = tmp_path / "fixture.luac"
    path.write_bytes(header + proto)
    result = analyze_lua_bytecode(str(path))
    assert result["ok"] is True, result
    assert result["instruction_count"] == 1
    assert result["block_count"] == 1
    assert result["ir"]["domain"] == "lua"


def test_planner_exposes_recovery_pipeline():
    from recovery_planner import build_recovery_plan
    plan = build_recovery_plan({
        "ok": True,
        "final_status": "PARTIAL_STRING_RECOVERY",
        "artifact_kind": "string_recovery",
        "strings_recovered": True,
    }, domain="lua")
    assert [stage["stage"] for stage in plan["pipeline"]] == [
        "observe", "route", "lift_ir", "cfg_ssa", "reconstruct", "validate", "promote"
    ]
    assert plan["pipeline"][2]["state"] == "pending"
