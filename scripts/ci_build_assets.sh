#!/bin/sh
# Build both runtimes at once. They use separate target directories, so the
# two cargo processes do not share a lock; both logs are kept.
set -eu
root=$(git rev-parse --show-toplevel)
cd "$root"
logs=${RUNNER_TEMP:-$(mktemp -d)}
python3 scripts/package-runtime.py > "$logs/production.log" 2>&1 &
production=$!
cargo build --locked --release --features fixture-http \
  --manifest-path rust-backend/Cargo.toml > "$logs/fixture-http.log" 2>&1 &
fixture=$!
status=0
wait "$production" || status=1
wait "$fixture" || status=1
cat "$logs/production.log" "$logs/fixture-http.log"
exit "$status"
