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


def test_corrupt_zlib_is_rejected_not_returned_as_plaintext():
    try:
        core.PakCompression.decompress_block(b"not-a-deflate-stream", None, core.CM_ZLIB)
    except ValueError as exc:
        assert "decompression failed" in str(exc).lower()
    else:
        raise AssertionError("corrupt compressed block was silently accepted")


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




def test_pak_v46_sm4_flag50_key_vector():
    # Captured from the first encrypted block of a v14 PAK entry.
    # This is the game-specific SM4 variant used by the PAK, not standards SM4.
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
            assert "output file count mismatch" in result["error"]
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
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("PAK EXTRACTION REGRESSION: PASS (6/6; marker-only authorization rejected)")


if __name__ == "__main__":
    main()
