#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT="ee07098c31e11601a9ca434bc12932a4ded65f7b"
TARGET="${ALVSIA_ANDROID_TARGET:-aarch64-linux-android}"
API="24"
NDK="${ANDROID_NDK_HOME:-}"
if [[ -z "$NDK" && -n "${ANDROID_HOME:-}" && -n "${ANDROID_NDK_VERSION:-}" ]]; then
  NDK="$ANDROID_HOME/ndk/$ANDROID_NDK_VERSION"
fi
if [[ -z "$NDK" || ! -d "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin" ]]; then
  echo "ANDROID_NDK_HOME or ANDROID_HOME/ANDROID_NDK_VERSION must identify an installed Linux Android NDK" >&2
  exit 2
fi
TOOLCHAIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
LINKER="$TOOLCHAIN/${TARGET}${API}-clang"
if [[ ! -x "$LINKER" || ! -x "$TOOLCHAIN/llvm-strip" ]]; then
  echo "Android linker/strip tools are missing from $TOOLCHAIN for target $TARGET" >&2
  exit 2
fi

WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
git init "$WORK/luau-decompiler"
git -C "$WORK/luau-decompiler" remote add origin https://github.com/PumbaaDev/luau-decompiler.git
git -C "$WORK/luau-decompiler" fetch --depth 1 origin "$COMMIT"
git -C "$WORK/luau-decompiler" checkout --detach FETCH_HEAD
test "$(git -C "$WORK/luau-decompiler" rev-parse HEAD)" = "$COMMIT"
grep -q '^license = "MIT"' "$WORK/luau-decompiler/Cargo.toml"
grep -q '^version = "0.2.0"' "$WORK/luau-decompiler/Cargo.toml"
test -s "$WORK/luau-decompiler/Cargo.lock"
test -s "$WORK/luau-decompiler/LICENSE"

cd "$WORK/luau-decompiler"
export ANDROID_NDK_HOME="$NDK"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$LINKER"
cargo build --locked --release -p luau-cli --target "$TARGET"
BIN="$WORK/luau-decompiler/target/$TARGET/release/luau-decompiler"
test -s "$BIN"
"$TOOLCHAIN/llvm-strip" --strip-all "$BIN"
if [[ "$TARGET" == "aarch64-linux-android" ]]; then readelf -h "$BIN" | grep -q "AArch64"; elif [[ "$TARGET" == "x86_64-linux-android" ]]; then readelf -h "$BIN" | grep -Eq "Advanced Micro Devices X86-64|X86-64"; else echo "Unsupported Android target: $TARGET" >&2; exit 2; fi
readelf -l "$BIN" | grep -q '/system/bin/linker64'

if [[ "$TARGET" == "aarch64-linux-android" ]]; then ABI="arm64-v8a"; LICENSE_SUFFIX="arm64"; elif [[ "$TARGET" == "x86_64-linux-android" ]]; then ABI="x86_64"; LICENSE_SUFFIX="x86_64"; else echo "Unsupported Android target: $TARGET" >&2; exit 2; fi
DEST="$ROOT/app/src/main/jniLibs/$ABI"
LICENSES="$ROOT/app/src/main/assets/engine_licenses"
mkdir -p "$DEST" "$LICENSES"
install -m 0755 "$BIN" "$DEST/libluau-decompiler-cli.so"
install -m 0644 LICENSE "$LICENSES/luau-decompiler-MIT.txt"
sha256sum "$DEST/libluau-decompiler-cli.so" > "$LICENSES/luau-decompiler-android-${LICENSE_SUFFIX}.sha256"
cat > "$LICENSES/luau-decompiler-android-${LICENSE_SUFFIX}.manifest" <<EOF
upstream=https://github.com/PumbaaDev/luau-decompiler
commit=$COMMIT
version=0.2.0
license=MIT
target=$TARGET
android_api=$API
ndk=$(basename "$NDK")
rust=$(rustc --version)
stripped=yes
supported_luau_bytecode=3-9
EOF
file "$DEST/libluau-decompiler-cli.so"
echo "Installed pinned PumbaaDev Luau decompiler for Android $ABI."
