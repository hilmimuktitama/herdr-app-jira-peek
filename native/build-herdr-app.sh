#!/bin/sh
# Build the optional desktop renderer extension without replacing installed apps.
set -eu
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
REVISION=36725d47c89cd19345994363d6d9cdee5c42c80b
build_root=${1:-"$ROOT/.local/herdr-app-highlight-source"}
for dependency in git cargo rustc zig; do
  command -v "$dependency" >/dev/null 2>&1 || { printf '%s is required\n' "$dependency" >&2; exit 1; }
done
[ "$(zig version)" = 0.16.0 ] || { printf 'Zig 0.16.0 is required\n' >&2; exit 1; }
case "$(rustc --version)" in
  'rustc 1.95.0 '*) ;;
  *) printf 'Rust 1.95.0 is required for the pinned desktop build\n' >&2; exit 1 ;;
esac
[ ! -e "$build_root" ] || { printf 'Choose a new, nonexistent build directory: %s\n' "$build_root" >&2; exit 1; }
git clone --depth 1 --branch v0.1.10 https://github.com/herdrdev/herdr-app.git "$build_root"
[ "$(git -C "$build_root" rev-parse HEAD)" = "$REVISION" ] || { printf 'Unexpected upstream revision\n' >&2; exit 1; }
git -C "$build_root" submodule update --init --depth 1
git -C "$build_root" apply --check "$ROOT/native/herdr-app-0.1.10-highlight.patch"
git -C "$build_root" apply "$ROOT/native/herdr-app-0.1.10-highlight.patch"
(cd "$build_root" && cargo build --release --locked)
mkdir -p "$ROOT/.local/bin"
install -m 755 "$build_root/target/release/herdr-app" "$ROOT/.local/bin/herdr-app-peek.new"
mv "$ROOT/.local/bin/herdr-app-peek.new" "$ROOT/.local/bin/herdr-app-peek"
printf 'Built %s\nSee native/APP-HIGHLIGHT.md for activation.\n' "$ROOT/.local/bin/herdr-app-peek"
