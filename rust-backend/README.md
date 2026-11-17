# Rust runtime

Since Jira Peek 0.10.0, installations use this process-per-operation replacement for the runtime
shell bridge. The JavaScript/GPUI panel stays in place. REST reads use libcurl
inside the executable without child utilities; TWG retains its CLI. There is no
daemon. The shell source remains an independent regression/benchmark oracle.

## Installation and distribution

For first installation, download all three files for your platform from the
same release into the source checkout's `.release-runtime` directory. The first
executable is your bootstrap; `manage install` verifies and stages the bundle.
Subsequent Rust release updates download and verify the new assets automatically.

| Platform | Executable filename |
| --- | --- |
| macOS Apple Silicon | `jira-peek-bridge-macos-aarch64` |
| macOS Intel | `jira-peek-bridge-macos-x86_64` |
| Linux arm64 | `jira-peek-bridge-linux-aarch64` |
| Linux x86_64 | `jira-peek-bridge-linux-x86_64` |

For each executable, also download `EXECUTABLE.json` and
`EXECUTABLE-NOTICES.txt`, preserving their original filenames. Assets are:
`jira-peek-bridge-{macos|linux}-{aarch64|x86_64}`, its `.json` manifest and
`-NOTICES.txt`. HTTPS, bounded downloads, SHA-256, source identity, release version,
architecture, protocol and production build information are checked in staging.
The stable executable identity must match; system libcurl/TLS version strings
may differ from the build host and are reported for diagnostics.
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
# Example for Apple Silicon; use the matching platform asset on other systems.
.release-runtime/jira-peek-bridge-macos-aarch64 manage doctor
.release-runtime/jira-peek-bridge-macos-aarch64 manage install --source-root "$PWD" --check --attach
```

The packager remaps compiler source paths so binaries do not disclose the build
machine’s home/worktree directories. It writes `.release-runtime/` and uses the separate
`rust-backend/target/production` build directory, always without fixture features.
An optional `--output /absolute/path` prepares assets for later review/upload;
copy all three platform files into `.release-runtime` for an offline install.
Build notices include the resolved dependency license texts. Doctor stays offline
and does not compile or download. The Rust crate's independent `0.1.0` version
and bridge protocol `1` are recorded alongside the mod release version.

Version 0.12.0 adds Rust lifecycle commands; 0.11.0 and earlier executables
do not contain them. A
matching prebuilt source/package installation needs no Python, jq, curl executable
or external SHA utility. Python remains a developer dependency for packaging,
tests and benchmarks. Git remains an explicit dependency for release updates.
The compiled executable still links libcurl/TLS and libc; TWG retains its CLI.
Release downloads, setup and reader requests honor `CURL_CA_BUNDLE` (or
`SSL_CERT_FILE`) and `SSL_CERT_DIR` for explicit trust configuration while
retaining certificate verification and HTTPS-only release downloads.

```text
jira-peek-bridge manage --help
jira-peek-bridge manage doctor [--json]
jira-peek-bridge manage install --source-root ABS [--app-home ABS] [--config-dir ABS] [--update] [--check] [--attach [LAYOUT]]
jira-peek-bridge manage update [--app-home ABS] [--version VERSION] [--check] [--allow-downgrade]
jira-peek-bridge manage rollback BACKUP_NAME [--app-home ABS] [--check]
jira-peek-bridge manage integration diagnose [--app-home ABS] [--layout NAME]
jira-peek-bridge manage integration repair [--app-home ABS] [--layout NAME]
```

Lifecycle commands return nonzero on failure with sanitized diagnostics. Setup
and reader commands keep the JSON error protocol. `manage --help` and
`manage <command> --help` succeed; unrecognized or duplicate lifecycle options
use `invalid_management_arguments`. Doctor checks herdr-app >=
0.1.10 and independent `hc` availability offline. Installed commands target their
own app home by default; explicit `--app-home` overrides it. Install and update
preserve the existing managed inventory, private settings, executable modes and
named backups. The frozen historical inventory is independent of current bundle
contents. Existing Python helpers remain compatible entry points and test oracles.
Frozen source profiles support the 24 existing numbered tags from 0.1.0 through
0.10.0, including 0.10.0's verified Rust assets and earlier shell inventories.
Other source versions must satisfy the current Rust distribution contract;
future inventory changes require corresponding installer support and are rejected
before replacement rather than silently omitting new mod files. The two regular
Herdr-generated files (`gpui-kit.d.ts`, `jsconfig.json`) are ignored in source.
Restoring an
older release restores that release's runtime dependencies. No legacy installer
code executes in the Rust installation path.

`--attach` prepares a personal layout and toolbar without selecting them. Explicit
planning/check failures stop installation; optional integration during updates
can fail while a valid code update succeeds. Read the reported state and repair
guidance. Diagnose is read-only; repair checks the managed bundle and toolbar,
preserves conflicting personal files and can complete a partial publication.
Neither command proves that a button rendered. Fresh bundles ship
`docs/PANEL-INTEGRATION.md`; repair guidance also names an online fallback.
A Rust update run by a lifecycle that predates the file may omit it; use the
online guide until the next source-based install.
A conflicting personal copy is reported by Rust `manage integration repair` as
`personal_integration_detected` with its preserved files. All paths must be absolute and
have no symlink ancestors; canonicalize conventional temporary aliases first.

The installed manifest hashes the executable and notices. The panel invokes the
executable directly; `runtime/app-bridge.sh` forwards legacy callers to it.
The in-app setup protocol uses this executable and libcurl, with no Python or
curl executable. Field editing uses the host's native file APIs. Configuration
and saved state retain their formats. Updates through older installed helpers work
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
discover CONFIG_DIRECTORY STATE_ROOT CONTEXT mine|text QUERY NEXT_PAGE_TOKEN
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
Primary coupled contracts are JP-021–025 and JP-026–035. The panel retains native
interaction, form state and field editing; the runtime implements the private
`setup inspect|prepare|save|cancel` protocol. Setup verifies the account before
activating settings, uses a credential-free tenant lookup for scoped tokens,
and keeps its 64 KiB response limit and 20-second timeout. The Python setup
source remains an independent compatibility oracle. No native UI or live Jira
verification is claimed by these tests.

## Offline verification

Standalone maintenance can clear one already initialized connection namespace:

```text
jira-peek-bridge manage clear-cache --state-dir ABSOLUTE_CONNECTION_DIRECTORY
```

Prefer the panel's Clear cache action, which also resets its in-memory state and
reconnects. The standalone command rejects shared roots, relative/traversing and
symlinked paths, shares the reader publication lock and advances the epoch even
when no cache directory exists. It removes only immediate regular cache files;
other state, symlinks and nested directories survive. Missing state is a read-only
no-op. It performs no network calls and invokes no utilities. Failure is a
sanitized stderr message and nonzero exit, unlike the JSON bridge error protocol.
The historical shell helper remains an independent oracle.

The complete lifecycle acceptance suite runs against a matching production
source package, a separate fixture-enabled binary for rejection tests, and an
immutable historical source fixture:

```sh
JIRA_PEEK_MANAGEMENT_BINARY=/absolute/production/jira-peek-bridge \
JIRA_PEEK_SOURCE_FIXTURE=/absolute/current-source \
JIRA_PEEK_FIXTURE_BINARY=/absolute/fixture/jira-peek-bridge \
JIRA_PEEK_LEGACY_SOURCE_FIXTURE=/absolute/v0.9.1-source \
python3 -B rust-backend/tests/lifecycle_acceptance_test.py -v
```

Use the complete v0.9.1 tag contents for the historical fixture. Current source
must include matching `.release-runtime` assets. The driver requires Python, a
C compiler, Git and OpenSSL; only its independent Python oracle check requires
curl. Product subprocesses use native host fixtures and deny Python/jq/curl/SHA
utilities, with a separate test where those tools are absent. HTTPS is routed
through a fictional-only loopback proxy; Git uses temporary local tags.
Assertions cover install → setup → reads → update → rollback, previous-state
preservation on setup failures, attachment/repair conflicts, fixture-binary
rejection and old/new helper transitions. Fixture host checks do not establish
native rendering or interaction. CI runs these contracts on all four targets;
local results cover only the platform actually tested.

For the complete historical management tests, prepare all frozen public sources
outside the checkout. This developer helper verifies tag/commit identity and
builds the historical 0.10.0 production assets with the selected Rust toolchain:

```sh
python3 -B scripts/prepare-lifecycle-fixtures.py --output /tmp/jira-peek-history-unique
JIRA_PEEK_HISTORICAL_SOURCES=/tmp/jira-peek-history-unique \
JIRA_PEEK_LEGACY_SOURCE=/tmp/jira-peek-history-unique/v0.9.1 \
JIRA_PEEK_MANAGEMENT_FIXTURE_BINARY=/absolute/fixture/jira-peek-bridge \
python3 -B -m unittest discover -s tests -p management_test.py -v
```

All fixtures contain invented identities and issues. Tests create private temporary
config/state; they never inspect a user's Jira setup. Build the special fixture
binary only for these tests and benchmarks:

```sh
cargo build --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml
cargo test --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml
cargo clippy --locked --release --features fixture-http --manifest-path rust-backend/Cargo.toml -- -D warnings
python3 rust-backend/tests/parity_test.py -v
python3 rust-backend/tests/clear_cache_test.py -v
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
JIRA_PEEK_PRODUCTION_BINARY=/absolute/path/to/production-binary python3 -B rust-backend/tests/setup_test.py -v
JIRA_PEEK_PRODUCTION_BINARY=/absolute/path/to/production-binary python3 -B rust-backend/tests/setup_transport_test.py -v
node --test rust-backend/tests/setup_controller.test.js
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


## Discovery protocol

`discover` is a REST-only read operation using POST `/rest/api/3/search/jql`,
verified against the official enhanced-search documentation on 2026-11-14.
My work requires an empty QUERY; text accepts a literal phrase (Lucene escaping
inside a JQL string) or an allowlisted uppercase key. Only project-name plus
numeric-suffix input takes the key path; hyphenated words remain literal text.
QUERY is capped at 512 UTF-8
bytes, tokens at 4096, pages at 50 and input responses at the existing 64 MiB
bound. Control characters are rejected. Fields use the existing picker projection.
Returned keys must pass the allowlist. No raw JQL or returned URL is executed.

Success adds `rows`, `nextPageToken` (empty when finished) and `isLast` to the
normal context envelope. Pages never write issue bodies or query caches. Context
and credential checks run before and after transport; authentication failure
revokes the connection epoch. Collection 403 does not invalidate unrelated bodies.
429 returns `rate_limited` with a bounded integer `retryAfter` in seconds (30 when
missing/invalid/date-form; maximum 86400). There are no runtime retries.
TWG returns `discovery_unsupported`. The shell oracle does not implement discovery;
production TLS tests exercise the new operation independently of legacy parity.
