from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_android_runner_configures_native_unluac_from_native_library_dir():
    kotlin = (
        ROOT / "app/src/main/java/com/alvsia/pro/tool/PythonBridgeRunner.kt"
    ).read_text(encoding="utf-8")
    bridge = (ROOT / "app/src/main/python/alvsia_bridge.py").read_text(encoding="utf-8")
    orchestrator = (
        ROOT / "app/src/main/python/lua_engine/orchestrator.py"
    ).read_text(encoding="utf-8")

    manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'android:extractNativeLibs="true"' in manifest
    assert "applicationInfo?.nativeLibraryDir" in kotlin
    assert 'File(nativeLibDir, "libunluac-cli.so")' in kotlin
    assert "nativeCli.canExecute()" in kotlin
    assert '"configure_unluac_rs"' in kotlin
    assert 'def configure_unluac_rs(v):return _bin("ALVSIA_UNLUAC_RS_BIN",v)' in bridge
    assert 'os.environ.get("ALVSIA_UNLUAC_RS_BIN", "")' in orchestrator


def test_android_native_unluac_build_is_pinned_and_installed_executable():
    build = (ROOT / "tools/build_unluac_rs_android.sh").read_text(encoding="utf-8")
    assert 'TAG="v1.4.4"' in build
    assert 'cargo build --locked --release -p unluac-cli --target "$TARGET"' in build
    assert 'install -m 0755 "$BIN" "$DEST/libunluac-cli.so"' in build
    assert 'readelf -l "$BIN" | grep -q \'/system/bin/linker64\'' in build
