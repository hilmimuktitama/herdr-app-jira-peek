#!/bin/sh
# Build the pinned native input fixes without replacing the installed host.
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
REVISION=4aa3460749947e7771aa39a8a2cec58d46649926
build_root=${1:-"$ROOT/.local/herdr-app-input-source"}
for dependency in git cargo rustc zig; do
  command -v "$dependency" >/dev/null 2>&1 || { printf '%s is required\n' "$dependency" >&2; exit 1; }
done
[ "$(zig version)" = 0.16.0 ] || { printf 'Zig 0.16.0 is required\n' >&2; exit 1; }
case "$(rustc --version)" in
  'rustc 1.95.0 '*) ;;
  *) printf 'Rust 1.95.0 is required for the pinned desktop build\n' >&2; exit 1 ;;
esac
[ ! -e "$build_root" ] || { printf 'Choose a new, nonexistent build directory: %s\n' "$build_root" >&2; exit 1; }
git clone --depth 1 --branch v0.1.12 https://github.com/herdrdev/herdr-app.git "$build_root"
[ "$(git -C "$build_root" rev-parse HEAD)" = "$REVISION" ] || { printf 'Unexpected upstream revision\n' >&2; exit 1; }
git -C "$build_root" submodule update --init --depth 1
git -C "$build_root" apply --check "$ROOT/native/herdr-app-input.patch"
git -C "$build_root" apply "$ROOT/native/herdr-app-input.patch"
(cd "$build_root" && cargo build --release --locked)
mkdir -p "$ROOT/.local/bin"
install -m 755 "$build_root/target/release/herdr-app" "$ROOT/.local/bin/herdr-app-input.new"
mv "$ROOT/.local/bin/herdr-app-input.new" "$ROOT/.local/bin/herdr-app-input"
printf 'Built %s\nSee native/APP-INPUT.md for testing and activation.\n' "$ROOT/.local/bin/herdr-app-input"
