import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))

from alvsia_core import SM4
from lua_string_recover import _xor_single, rank_xor_candidates, recover_strings


def test_sm4_known_answer_vector():
    key = bytes.fromhex("0123456789abcdeffedcba9876543210")
    plaintext = bytes.fromhex("0123456789abcdeffedcba9876543210")
    expected = bytes.fromhex("681edf34d206965e86b3e94f536e4246")
    assert SM4(key).encrypt(plaintext) == expected
    assert SM4(key).decrypt(expected) == plaintext


def test_xor_candidate_ranking_is_deterministic_and_key_aware():
    plaintext = b"function PlayerCharacter local Server RPC self " * 8
    encoded = _xor_single(plaintext, 0x18)
    first = rank_xor_candidates(encoded)
    second = rank_xor_candidates(encoded)
    assert first == second
    assert first[0]["key"] == 0x18
    assert first[0]["keyword_hits"] > 0


def test_string_recovery_report_is_bounded_and_honest():
    plaintext = b"function PlayerCharacter local Server RPC self " * 600
    encoded = _xor_single(plaintext, 0x18)
    with tempfile.TemporaryDirectory() as td:
        report = recover_strings(encoded, Path(td), "sample")
        assert report["best_key"] == "xor_18"
        assert report["candidate_count"] == len(report["steps"]) - 1 or report["candidate_count"] > 0
        output = Path(td) / "sample_strings_xor_18.txt"
        assert output.is_file()
        assert len(output.read_text(encoding="utf-8").splitlines()) <= 20_000
        assert "keyword_hits" in report
