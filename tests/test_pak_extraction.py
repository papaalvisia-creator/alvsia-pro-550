"""Regression tests for fail-closed PAK block extraction."""
import sys
import tempfile
import zlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))
import alvsia_core as core


def test_zlib_and_raw_deflate_blocks():
    plain = (b"Lua protected payload regression\n" * 200)
    wrapped = zlib.compress(plain)
    assert core.PakCompression.decompress_block(wrapped, None, core.CM_ZLIB) == plain

    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    raw = compressor.compress(plain) + compressor.flush()
    assert core.PakCompression.decompress_block(raw, None, core.CM_ZLIB) == plain


def test_zstd_plain_block_uses_zero_argument_decoder():

    """Regression for python-zstandard rejecting ZstdDecompressor(None)."""
    try:
        import zstandard as zstd
    except ImportError:
        raise AssertionError("zstandard dependency is required for PAK ZSTD support")

    plain = (b"ALVSIA PAK ZSTD regression payload\\n" * 128)
    compressed = zstd.ZstdCompressor(level=3).compress(plain)
    assert core.PakCompression.decompress_block(compressed, None, core.CM_ZSTD) == plain

    # A dictionary-compressed block must still require an actual dictionary;
    # never silently pass None into the dictionary constructor.
    dictionary = zstd.ZstdCompressionDict(b"ALVSIA dictionary regression seed")
    with_dict = zstd.ZstdCompressor(dict_data=dictionary).compress(plain)
    assert core.PakCompression.decompress_block(
        with_dict, dictionary, core.CM_ZSTD_DICT
    ) == plain
    try:
        core.PakCompression.decompress_block(with_dict, None, core.CM_ZSTD_DICT)
    except (ValueError, TypeError, zstd.ZstdError):
        pass
    else:
        raise AssertionError("dictionary-compressed block accepted without dictionary")


def test_explicit_zstd_frame_is_recovered_when_index_marks_zlib():
    try:
        import zstandard as zstd
    except ImportError:
        raise AssertionError("zstandard dependency is required for PAK ZSTD support")

    plain = b"ALVSIA ZSTD frame-magic fallback regression\\n" * 256
    frame = zstd.ZstdCompressor(level=3).compress(plain)
    assert frame[:4] == b"\\x28\\xb5\\x2f\\xfd"

    recovered = core.PakCompression.decompress_block(
        frame, None, core.CM_ZLIB, max_output_size=len(plain)
    )
    assert recovered == plain

    try:
        core.PakCompression.decompress_block(
            frame, None, core.CM_ZLIB, max_output_size=len(plain) - 1
        )
    except Exception as exc:
        assert "size" in str(exc).lower() or "limit" in str(exc).lower() or "max" in str(exc).lower()
    else:
        raise AssertionError("ZSTD fallback exceeded the declared output limit")


def test_corrupt_zlib_is_rejected_not_returned_as_plaintext():
    try:
        core.PakCompression.decompress_block(b"not-a-deflate-stream", None, core.CM_ZLIB)
    except ValueError as exc:
        assert "decompression failed" in str(exc).lower()
    else:
        raise AssertionError("corrupt compressed block was silently accepted")


def test_corrupt_zlib_with_nonstandard_trailer_decodes_leniently():
    """Game-written zlib frames carry a non-standard trailing checksum word.

    The DEFLATE body itself is intact; the engine decodes it leniently and the
    entry-level SHA-1 content-hash gate provides the cryptographic integrity
    check. A truncated body must still fail closed.
    """
    plain = b"lenient zlib regression payload\n" * 16
    wrapped = zlib.compress(plain)
    # Corrupt only the trailing ADLER32 word; the deflate body stays valid.
    broken = wrapped[:-4] + b"\x00\x00\x00\x00"
    result = core.PakCompression.decompress_block(broken, None, core.CM_ZLIB)
    assert result == plain
    # A truncated deflate body must NOT decode.
    try:
        core.PakCompression.decompress_block(wrapped[: len(wrapped) - 12], None, core.CM_ZLIB)
    except ValueError as exc:
        assert "decompression failed" in str(exc).lower()
    else:
        raise AssertionError("truncated deflate body was silently accepted")


def test_write_is_atomic_and_checks_decompressed_size():
    plain = b"Lua payload: validated"
    compressed = zlib.compress(plain)
    pak = core.TencentPakFile.__new__(core.TencentPakFile)
    pak._file_content = memoryview(compressed)
    pak._zstd_dict = None
    entry = SimpleNamespace(
        encryption_method=0,
        compression_method=core.CM_ZLIB,
        compressed_blocks=[SimpleNamespace(start=0, end=len(compressed))],
        encrypted=False,
        uncompressed_size=len(plain),
        compression_block_size=0,
    )
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "sample.lua"
        dest.write_bytes(b"old-output-must-not-survive-as-success")
        pak._write_to_disk(dest, entry)
        assert dest.read_bytes() == plain
        assert not Path(str(dest) + ".alvsia-tmp").exists()

        corrupt_entry = SimpleNamespace(
            encryption_method=0,
            compression_method=core.CM_ZLIB,
            compressed_blocks=[SimpleNamespace(start=0, end=len(b"corrupt"))],
            encrypted=False,
            uncompressed_size=100,
            compression_block_size=0,
        )
        pak._file_content = memoryview(b"corrupt")
        dest.write_bytes(b"keep-prior-file-if-operation-fails")
        try:
            pak._write_to_disk(dest, corrupt_entry)
        except ValueError:
            pass
        else:
            raise AssertionError("corrupt entry did not fail")
        assert dest.read_bytes() == b"keep-prior-file-if-operation-fails"
        assert not Path(str(dest) + ".alvsia-tmp").exists()




def _authorize_synthetic_sm4():
    """Install a synthetic SM4 candidate registry for cipher round-trip tests.

    Synthetic test keys only: no production/game/server material is embedded
    in this repository. Real deployments supply authorized candidates at
    runtime via alvsia_core.set_authorized_sm4_candidates().
    """
    synthetic = ("ALVSIA-SYNTHETIC-CANDIDATE-0001", "ALVSIA-SYNTHETIC-CANDIDATE-0002")
    assert core.set_authorized_sm4_candidates(synthetic)


def test_sm4_new_method_derivation_is_deterministic_and_fails_closed():
    """Method >= 32 derives its key from the authorized candidate registry."""
    _authorize_synthetic_sm4()
    try:
        path = Path("Test_Entry_Name.uasset")
        key_a = core.PakCrypto._derive_sm4_key(path, 50)
        key_b = core.PakCrypto._derive_sm4_key(path, 50)
        assert key_a == key_b
        # Same stem, different new-method indexes must not collide.
        keys = {
            core.PakCrypto._derive_sm4_key(path, method)
            for method in (32, 50, 51, 53)
        }
        assert len(keys) == 4
        # Without authorization the new-method path must fail closed.
        core.clear_authorized_sm4_candidates()
        try:
            core.PakCrypto._derive_sm4_key(path, 50)
        except RuntimeError as exc:
            assert "not authorized" in str(exc)
        else:
            raise AssertionError("unauthorized SM4 derivation did not fail closed")
    finally:
        core.clear_authorized_sm4_candidates()


def test_sm4_game_variant_roundtrip_with_synthetic_material():
    """SM4 encrypt/decrypt round-trip through the game's SM4 S-box variant."""
    _authorize_synthetic_sm4()
    try:
        path = Path("Test_Entry_Name.uasset")
        block = bytes(range(64))
        cipher = core.PakCrypto._decrypt_sm4(block, path, 50)
        assert cipher != block
        restored = core.PakCrypto._encrypt_sm4_block(cipher, path, 50)
        assert restored == block
    finally:
        core.clear_authorized_sm4_candidates()


def test_pak_v46_sm4_flag50_key_vector():
    """Captured from the first encrypted block of a v14 PAK entry (method 50).

    The verification material (candidate secret list) is authorized local
    configuration; it is intentionally NOT embedded in this public repository.
    When the operator supplies ALVSIA_TEST_SM4_CANDIDATES_FILE (one candidate
    per line), the exact captured vector is asserted; otherwise the test skips
    with the authorization blocker stated explicitly - it never fakes a pass.
    """
    import os
    import pytest
    candidates_file = os.environ.get("ALVSIA_TEST_SM4_CANDIDATES_FILE", "")
    if not candidates_file or not Path(candidates_file).is_file():
        pytest.skip(
            "SM4 candidate material is not authorized/supplied "
            "(set ALVSIA_TEST_SM4_CANDIDATES_FILE to the operator-provided list)"
        )
    candidates = [
        line.strip()
        for line in Path(candidates_file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert core.set_authorized_sm4_candidates(candidates)
    path = Path("Lobby_VersionUpdateSlap_Page_002_UIBP.uasset")
    cipher = bytes.fromhex("dc91fe9cf0e2f652416102fe148da3e8")
    key = core.PakCrypto._derive_sm4_key(path, 50)
    assert key.hex() == "d3af220809b6ac0b1225b9812c3f8788"
    assert core.PakCrypto._decrypt_sm4(cipher, path, 50).hex() == (
        "789ced9c797414c5bac02b9000212b09"
    )


def test_unpack_refuses_skipped_entries_and_output_count_mismatch():
    import os
    original_class = core.TencentPakFile
    original_require = core._alvsia_require_operation
    original_proof = getattr(core, "_ALVSIA_CORE_ACTIVE_PROOF", None)
    old_session = os.environ.get("ALVSIA_APK_SESSION")
    old_token = os.environ.get("ALVSIA_SESSION_TOKEN")
    os.environ["ALVSIA_APK_SESSION"] = "1"
    os.environ.pop("ALVSIA_SESSION_TOKEN", None)
    core._alvsia_clear_operation_proof()
    try:
        core._alvsia_require_operation(("pak.unpack",))
    except RuntimeError as exc:
        assert "Operation authorization failed" in str(exc)
    else:
        raise AssertionError("session marker alone must not authorize PAK unpack")

    # Isolate extraction-integrity behavior from the production authorization
    # gate; the gate itself is asserted above to reject a marker-only session.
    core._alvsia_require_operation = lambda _allowed: True

    class FakePak:
        def __init__(self, _path):
            pass

        def dump(self, out_dir):
            Path(out_dir, "one.lua").write_bytes(b"one")
            return {
                "expected_files": 2,
                "written_files": 1,
                "skipped_directories": 0,
                "skipped_files": 1,
            }

    try:
        core.TencentPakFile = FakePak
        with tempfile.TemporaryDirectory() as td:
            result = core.run_pak_unpack("synthetic.pak", Path(td) / "out")
            assert not result["ok"]
            assert "incomplete PAK extraction" in result["error"]

        class MismatchedOutputPak:
            def __init__(self, _path):
                pass

            def dump(self, out_dir):
                Path(out_dir, "only-one.lua").write_bytes(b"one")
                return {
                    "expected_files": 2,
                    "written_files": 2,
                    "skipped_directories": 0,
                    "skipped_files": 0,
                }

        core.TencentPakFile = MismatchedOutputPak
        with tempfile.TemporaryDirectory() as td:
            result = core.run_pak_unpack("synthetic.pak", Path(td) / "out")
            assert not result["ok"]
            assert "incomplete PAK extraction" in result["error"] and "on_disk=1" in result["error"]
    finally:
        core.TencentPakFile = original_class
        core._alvsia_require_operation = original_require
        core._ALVSIA_CORE_ACTIVE_PROOF = original_proof
        if old_session is None:
            os.environ.pop("ALVSIA_APK_SESSION", None)
        else:
            os.environ["ALVSIA_APK_SESSION"] = old_session
        if old_token is None:
            os.environ.pop("ALVSIA_SESSION_TOKEN", None)
        else:
            os.environ["ALVSIA_SESSION_TOKEN"] = old_token


def main():
    tests = (
        test_zlib_and_raw_deflate_blocks,
        test_zstd_plain_block_uses_zero_argument_decoder,
        test_corrupt_zlib_is_rejected_not_returned_as_plaintext,
        test_write_is_atomic_and_checks_decompressed_size,
        test_pak_v46_sm4_flag50_key_vector,
        test_unpack_refuses_skipped_entries_and_output_count_mismatch,
    )
    # This file is also executed directly (``python3 tests/test_pak_extraction.py``)
    # by the Android Security Validation workflow. A test that calls
    # ``pytest.skip()`` raises ``Skipped``; when run as a plain script that
    # exception is otherwise uncaught and turns an honest skip (e.g. SM4 key
    # material not supplied) into a hard exit-code-1 failure. Honour skips here
    # exactly as pytest would, without weakening any assertion.
    import pytest
    skipped = 0
    for test in tests:
        try:
            test()
        except pytest.skip.Exception as exc:  # noqa: PT009 - script runner
            skipped += 1
            print("SKIP", test.__name__, "-", exc)
            continue
        print("PASS", test.__name__)
    executed = len(tests) - skipped
    print(
        f"PAK EXTRACTION REGRESSION: PASS ({executed}/{len(tests)} executed, "
        f"{skipped} skipped; marker-only authorization rejected)"
    )


if __name__ == "__main__":
    main()
