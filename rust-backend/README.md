# Rust runtime

Jira Peek 0.10.0 installs this process-per-operation replacement for the runtime
shell bridge. The JavaScript/GPUI panel stays in place. REST reads use libcurl
inside the executable without child utilities; TWG retains its CLI. There is no
daemon. The shell source remains an independent regression/benchmark oracle.

## Installation and distribution

Published installations fetch three exact-version assets for the current platform:
`jira-peek-bridge-{macos|linux}-{aarch64|x86_64}`, its `.json` manifest and
`-NOTICES.txt`. HTTPS, bounded downloads, SHA-256, source identity, release version,
architecture, protocol and production build information are checked in staging.
Missing, modified, fixture-enabled or incompatible assets fail before replacement.
These checks establish integrity against the trusted release manifest; assets are
not independently signed/notarized. GitHub release access remains a trust boundary.

Release CI builds on macOS 15 and Ubuntu 22.04 for both architectures. Linux uses
system libcurl/TLS and glibc 2.35+; macOS uses system libcurl. Local acceptance on
one OS version does not establish the complete compatibility matrix. CI artifacts
must pass on all four targets before publication. No binary is committed to Git.

For an unpublished checkout or offline install, build the matching production
package first (Rust/Cargo 1.93.1+, C compiler and libcurl development libraries;
Linux also needs pkg-config). Cargo may download its locked dependencies:

```sh
python3 scripts/package-runtime.py
python3 scripts/install-app.py --check --attach
```

The packager remaps compiler source paths so binaries do not disclose the build
machine’s home/worktree directories. It writes `.release-runtime/` and uses the separate
`rust-backend/target/production` build directory, always without fixture features.
An optional `--output /absolute/path` prepares assets for later review/upload;
copy all three platform files into `.release-runtime` for an offline install.
Build notices include the resolved dependency license texts. Doctor stays offline
and does not compile or download. The Rust crate's independent `0.1.0` version
and bridge protocol `1` are recorded alongside the mod release version.

The installed manifest hashes the executable and notices. The panel invokes the
executable directly; `runtime/app-bridge.sh` forwards legacy callers to it.
Setup/field editing retain their existing Python/shell dependencies. Configuration
and saved state are not rewritten. Updates through older installed helpers work
without a new flag. Current rollback preserves executable permissions; after
rolling back to a shell release, use the retained **0.10.0+** helper to restore a
Rust backup. Historical helpers do not preserve executable modes.

Build a production executable (Rust/Cargo, a C compiler and libcurl development libraries
required; macOS supplies libcurl, Linux commonly uses `libcurl4-openssl-dev`):

```sh
cargo build --locked --release --manifest-path rust-backend/Cargo.toml
```

Call `rust-backend/target/release/jira-peek-bridge` with the same positional
arguments as the shell bridge:

```text
config CONFIG_DIRECTORY STATE_ROOT
stamp CONFIG_DIRECTORY STATE_ROOT
clear CONFIG_DIRECTORY STATE_ROOT CONTEXT
issue CONFIG_DIRECTORY STATE_ROOT CONTEXT KEY [refresh|""] [READER_FIELDS]
metadata CONFIG_DIRECTORY STATE_ROOT CONTEXT KEY [KEY...]
comments CONFIG_DIRECTORY STATE_ROOT CONTEXT KEY [READER_FIELDS]
```

Directories must be absolute. Success and errors are JSON on stdout, with no
transport diagnostics or credentials on stderr; reported operational errors keep
exit status zero, matching the shell adapter. Configuration is parsed as literal
allowlisted assignments. REST uses libcurl inside this process, with system TLS trust
validation, HTTPS destinations, no redirects, 5-second connection and 30-second
request timeouts. Tokens stay out of subprocess arguments/environment. TWG uses
its configured executable directly with argument arrays; REST never invokes it.
The shell-only `CURL_BIN_PATH` executable override is not used by Rust; routing,
proxy and trust settings must be expressible through libcurl's supported options.
`--build-info` reports protocol, version, architecture, libcurl/TLS versions and
whether fixture routing was compiled in. It reads no configuration. A production
binary must report `fixtureTransport:false`.

Connection namespaces use the same SHA-256 of device/inode identity. Config and
auth fingerprints, epochs, private directories, marker files, cache signatures,
raw cache shapes, mtime timestamps, per-key generations and owner-token locks are
compatible with the shell backend. Network calls do not hold publication locks.
A newer miss supersedes an older attempt even when the newer attempt fails;
permission failures cannot delete a newer attempt's data. Cache snapshots are
validated and projected under the connection lock. TTL zero keeps responses only
in memory and clears durable payloads. Stamp and stale Clear remain local-only.
Legacy shell temporaries are reaped only for dead owners; known fixed diagnostics
are retained and obsolete raw diagnostics scrubbed. Identity changes retire
legacy session/source key files without following symlinks. Config `KEY_RE` is
inert but validated in process with libc regex: GNU egrep syntax on glibc,
Darwin grep's enhanced ERE flags on macOS, and POSIX ERE elsewhere. Direct
grep comparisons cover ordinary patterns, malformed intervals, brackets,
leading operators and backreferences on the tested platforms.

Projection ports `fields.jq`, `app-issue.jq` and `app-metadata.jq`: picker values,
ADF plain text, ordinary and merged tables, linked-issue structures, comments,
Unicode character limits, private object filtering and aggregate output bounds.
Primary coupled contracts are JP-022–024 and JP-026–035; setup/field editing remain
with the existing application (JP-021/025). No native UI or live Jira verification
is claimed by these tests.

## Offline verification

All fixtures contain invented identities and issues. Tests create private temporary
config/state; they never inspect a user's Jira setup. Build the special fixture
binary only for these tests and benchmarks:

```sh
cargo build --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml
cargo test --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml
cargo clippy --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml -- -D warnings
python3 rust-backend/tests/parity_test.py -v
python3 benchmarks/bridge.py --samples 60 --warmup 5
```

`fixture-http` permits `JIRA_PEEK_FIXTURE_HTTP` to redirect transport only to an
IP-literal loopback HTTP(S) endpoint, retaining the fictional original host for
netrc matching. **Never use this test build with real configuration.** The feature
is off by default. Production ignores both that variable and
`JIRA_PEEK_FIXTURE_CA`, which adds the generated test CA only during fixture
routing. Certificate verification stays enabled and system trust is untouched.
Rebuild without features before considering local integration.
Keep immutable copies of production and fixture executables when testing both;
Cargo's default output path is shared across feature selections. Never rebuild
an executable while a test or native fixture is using it.

The production transport suite requires a separate production executable, not
the fixture build used by parity tests:

```sh
JIRA_PEEK_PRODUCTION_BINARY=/absolute/path/to/production-binary python3 rust-backend/tests/transport_test.py -v
```

It uses a loopback CONNECT proxy that routes only `jira.example.test:443` to its
fictional TLS server. It checks proxy environment handling, trusted/untrusted
certificates, netrc authentication, ignored `.curlrc` and fixture overrides, and
issue/metadata/comment reads with no utility executables on PATH. No system trust
or user credentials are changed. Parity tests also compare netrc syntax directly
with actual curl, including case-insensitive hostnames, defaults, quotes and macros.

The parity harness subclasses the shell contract tests, including the shared
auth-revocation and configuration-swap regressions. Exclusions are named with reasons in `tests/parity_test.py`: source-injection
barriers and shell-specific utilities. Packaged installation is verified separately
by the main Python suite, including execution outside the source checkout. Replacement tests cover
utility-free REST, ordered failures, auth rotation, shell/Rust cache interchange,
marker safety, redirects and direct jq comparison. Tests do not establish full
parity for every curl/netrc/TWG version or operating system.

## Remaining differences and acceptance gaps

- Native acceptance must be established with the exact host and backend under
  test; successful current runs do not explain earlier intermittent host focus/render
  stalls or establish live Jira access. Release CI and downloadable assets must
  be checked on the exact publication commit before publishing.
- libcurl and the shell's curl executable may use different versions or TLS
  providers on a target machine. Their complete configuration compatibility is
  not established by the controlled netrc/proxy/TLS fixtures.
- Legacy accepted COLOR_THEME values follow the
  current shell oracle despite the product dictionary's stricter prose.
- Input files/REST JSON are capped at 64 MiB and serde's nesting limit applies.
  Shell responses have no equivalent input cap. Both bound projected output.
- TWG still launches its CLI for identity and reads, with the existing CLI's
  process behavior. This runtime does not add a TWG timeout or output cap.
- The runtime writes only fixed sanitized failure diagnostics; it does not
  reproduce every shell diagnostic string. Cache and epoch invalidation and
  guarded legacy-state cleanup are covered by shared tests.
- TTL-zero fetchedAt records in-memory receipt/publication time, instead of
  creating a temporary payload just to obtain filesystem mtime.

Benchmark reports belong under `/tmp/jira-peek-perf-evidence`, never this tree.
The harness alternates implementations, checks equivalent JSON (excluding
contexts/timestamps), records each sample and HTTP request count, and reports
median plus nearest-rank p95 and the 50% reduction target. It uses identical
loopback HTTPS responses, in-process libcurl, and actual curl via an exec-only
fixture routing wrapper for the shell baseline. Request counts are asserted;
metadata contains two rows, issue bodies and comments contain fictional text. It measures bridge process latency, not real Jira network latency
or panel redraw performance. TLS initialization and certificate verification are
included. Benchmark reports identify the exact binary and its libcurl/TLS versions.

## Replacement decision

The single-process runtime is selected for 0.10.0 after equivalent local HTTPS
fixtures exceeded the 50% median/p95 reduction target on tested macOS and Linux
arm64 systems, with parity, production TLS/proxy checks and native fictional
interaction checks. Measurements are fixture-specific and do not predict live
Jira latency. Preserve the shell oracle for comparisons; adding a daemon is not
justified by the measured local process cost. Full release-platform CI remains a
publication gate, separate from local acceptance.
