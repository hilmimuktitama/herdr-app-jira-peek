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

## Transactional setup

Compare the Python/curl setup oracle with the production Rust setup protocol:

```sh
python3 benchmarks/setup.py --binary /absolute/production/jira-peek-bridge \
  --samples 40 --warmup 5 --repeats 3 \
  --output /tmp/jira-peek-setup-unique-run.json
```

Use a release build without `fixture-http`, and a new output path for every run.
The report is marked incomplete before fixture initialization and refuses to
overwrite an existing report. It preserves raw samples, per-repeat median/p95,
HTTP counts, source hashes, executable identity and transport versions. The
binary and Python helper are copied before measurement. Run without concurrent
builds/tests or interactive app workloads when collecting performance evidence.

Each repeat creates new fictional connection roots, establishes a connection,
then alternates Python/Rust order with warmups per operation. Operation order
rotates between repeats. Inspect, prepare, cancel and save timings include
process startup, execution, output transfer and text decoding; JSON validation
is outside those timings. Transaction timing includes prepare, writing the
fictional submission and save, plus driver JSON handling between those steps.
Preparing inputs and cleaning up tickets for individual operations are untimed.
Inspect compares returned settings; all calls must succeed. Save/transaction
require exactly one authenticated GET to the fictional account endpoint; local
operations require zero HTTP calls.

The shared acceptance TLS fixture uses an ephemeral CA and loopback CONNECT
proxy; it never resolves or contacts Jira. Python invokes actual curl, Rust uses
in-process libcurl. Developer Python, curl, OpenSSL and Git are benchmark-driver
requirements, not new Rust runtime requirements. This compares implementation
stacks with warm filesystem state and a small classic-token account response.
It does not measure first installation, scoped-token setup, real network latency,
native input-to-paint time, CPU or memory. Repeats and raw samples expose local
variability; p95 values are empirical nearest-rank estimates, not confidence
intervals. No percentage target is treated as an acceptance gate.
