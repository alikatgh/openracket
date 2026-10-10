#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
cargo fmt --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked -- --test-threads=1
RACKET_BIN=${RACKET_BIN:-${RACKET_EXECUTABLE:-racket}}
export RACKET_BIN
if command -v "$RACKET_BIN" >/dev/null 2>&1; then
  RACKET_EXECUTABLE=$RACKET_BIN
  export RACKET_EXECUTABLE
  cargo test --lib --locked -- --ignored --test-threads=1
  cargo test --bin openracket --locked qa_real_app -- --ignored --test-threads=1
  python3 runtime-tests/test_bridge.py
  python3 qa/test_runtime_adversarial.py
else
  printf '%s\n' 'Racket runtime checks skipped: set RACKET_BIN or install racket on PATH.'
fi
