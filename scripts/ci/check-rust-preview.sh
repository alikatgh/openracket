#!/usr/bin/env bash
# Fail closed and record each actual result. No GUI/native-parity claim.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${RUNNER_TEMP:?}"
: "${RACKET_BIN:?Install verified Racket first}"
export RACKET_EXECUTABLE="$RACKET_BIN" RACKET="$RACKET_BIN"
[[ -x "$RACKET_BIN" ]]
[[ $(rustc --version) == 'rustc 1.94.0 '* ]]
report="$RUNNER_TEMP/openracket-rust-summary.md"
printf '# Preserved Rust preview: %s / %s\n\n' "$(uname -s)" "$(uname -m)" > "$report"
printf 'Commit: %s\n\n' "${GITHUB_SHA:-local}" >> "$report"
failure=0
run_check() {
  local label=$1; shift
  printf '\n=== %s ===\n' "$label"
  printf -- '- %s: STARTED\n' "$label" >> "$report"
  if "$@"; then
    printf -- '  Result: PASS\n' >> "$report"
  else
    local result=$?
    failure=1
    printf -- '  Result: FAIL (exit %s)\n' "$result" >> "$report"
  fi
}
# This manifest covers the preserved core, excluding CI scripts.
run_check frozen-core shasum -a 256 -c qa/release-source-sha256.txt
run_check format cargo fmt --check
run_check clippy cargo clippy --all-targets --locked -- -D warnings
run_check rust-tests cargo test --locked -- --test-threads=1
run_check real-racket-supervisor cargo test --lib --locked real_racket -- --ignored --test-threads=1
run_check real-racket-application cargo test --bin openracket --locked qa_real_app -- --ignored --test-threads=1
run_check bridge-python python3 runtime-tests/test_bridge.py
run_check adversarial-python python3 qa/test_runtime_adversarial.py
run_check native-debug-build cargo build --locked
printf '\nNative development build only; no distributable, signing, GUI automation or production-readiness claim.\n' >> "$report"
exit "$failure"
