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
