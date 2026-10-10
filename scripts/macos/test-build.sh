#!/usr/bin/env bash
# All results are native execution only when this script is run on the target Mac.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || {
  echo 'Requires an Apple Silicon macOS host.' >&2; exit 1;
}
: "${RACKET_BIN:?Install and verify real Racket before testing}"
export RACKET_EXECUTABLE="$RACKET_BIN" RACKET="$RACKET_BIN"
[[ -x "$RACKET_BIN" ]] || { echo 'No real Racket executable.' >&2; exit 1; }
[[ $(rustc --version) == 'rustc 1.94.0 '* ]] || { echo 'Rust 1.94.0 required.' >&2; exit 1; }
mkdir -p qa/macos-run
: > qa/macos-run/status.tsv
failure=0
run_check() {
  local label=$1; shift
  printf '\n=== %s ===\n' "$label"
  if "$@" > "qa/macos-run/$label.log" 2>&1; then
    printf '%s\tPASS\n' "$label" >> qa/macos-run/status.tsv
  else
    local result=$?
    failure=1
    printf '%s\tFAIL (exit %s)\n' "$label" "$result" >> qa/macos-run/status.tsv
  fi
  cat "qa/macos-run/$label.log"
}
run_check frozen-core shasum -a 256 -c qa/release-source-sha256.txt
run_check format cargo fmt --check
run_check clippy cargo clippy --all-targets --locked -- -D warnings
run_check rust-tests cargo test --locked -- --test-threads=1
run_check real-racket-supervisor cargo test --lib --locked real_racket -- --ignored --test-threads=1
run_check real-racket-application cargo test --bin openracket --locked qa_real_app -- --ignored --test-threads=1
run_check bridge-python python3 runtime-tests/test_bridge.py
run_check adversarial-python python3 qa/test_runtime_adversarial.py
if [[ $failure == 0 ]]; then
  run_check release-build cargo build --release --locked
else
  printf 'release-build\tNOT RUN (tests failed)\n' >> qa/macos-run/status.tsv
fi
python3 scripts/macos/write-report.py
exit "$failure"
