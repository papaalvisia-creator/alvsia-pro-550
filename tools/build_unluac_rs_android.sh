#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="v1.4.4"
TARGET="aarch64-linux-android"
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
LINKER="$TOOLCHAIN/aarch64-linux-android${API}-clang"
if [[ ! -x "$LINKER" || ! -x "$TOOLCHAIN/llvm-strip" ]]; then
  echo "Android ARM64 linker/strip tools are missing from $TOOLCHAIN" >&2
  exit 2
fi

WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
git clone --depth 1 --branch "$TAG" https://github.com/x3zvawq/unluac-rs.git "$WORK/unluac-rs"
cd "$WORK/unluac-rs"
test "$(grep -m1 '^version = ' Cargo.toml | cut -d '"' -f2)" = "1.4.4"
grep -q '^license = "MIT"' Cargo.toml
test -s LICENSE.txt

export ANDROID_NDK_HOME="$NDK"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$LINKER"
cargo build --locked --release -p unluac-cli --target "$TARGET"
BIN="$WORK/unluac-rs/target/$TARGET/release/unluac-cli"
test -s "$BIN"
"$TOOLCHAIN/llvm-strip" --strip-all "$BIN"
readelf -h "$BIN" | grep -q 'AArch64'
readelf -l "$BIN" | grep -q '/system/bin/linker64'

DEST="$ROOT/app/src/main/jniLibs/arm64-v8a"
mkdir -p "$DEST" "$ROOT/app/src/main/assets/engine_licenses"
install -m 0755 "$BIN" "$DEST/libunluac-cli.so"
install -m 0644 LICENSE.txt "$ROOT/app/src/main/assets/engine_licenses/unluac-rs-MIT.txt"
sha256sum "$DEST/libunluac-cli.so" > "$ROOT/app/src/main/assets/engine_licenses/unluac-rs-android-arm64.sha256"
file "$DEST/libunluac-cli.so"
echo "Installed pinned unluac-rs $TAG for Android ARM64."
