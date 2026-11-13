# Fictional bridge benchmarks

Build the opt-in Rust fixture executable and run from the repository root:

```sh
cargo build --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml
python3 benchmarks/bridge.py --samples 60 --warmup 5
```

Results default to `/tmp/jira-peek-perf-evidence/bridge-benchmark.json`. Use
`--output` to choose another location outside this repository. The harness runs
stamp, config, cached issue, forced issue, bulk metadata and comments, alternating
order with five warmups and 60 measured calls per implementation per operation.
Each sample includes process startup, projection and JSON serialization. It
asserts matching JSON and HTTP counts (zero for cache/stamp/config, one for each
uncached operation). Metadata contains two rows; issue descriptions and 100
comments exercise projections.
The report records start/end times and sets `completed:true` only after all six
operations finish; an interrupted partial report is not acceptance evidence.
The server and every config, credential and issue are fictional; no existing
configuration is read. Rust uses in-process libcurl; the shell invokes actual curl through an exec-only
wrapper. Both use the same loopback HTTPS server and generated test CA. OpenSSL
is needed to generate the temporary certificate; no trust store is changed.
The wrapper only supplies local routing and CA trust, without a Python process
per request. This measures local fixture latency, not real Jira service latency. No server
is left running when the harness exits. Test HTTP routing is compile-time gated;
see `rust-backend/README.md` for limitations and production build instructions.
