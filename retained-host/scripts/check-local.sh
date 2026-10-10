#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PLTUSERHOME="$PWD/profile"
export XDG_CACHE_HOME="$PWD/profile/.cache"
RACKET="${RACKET:-/workspace/shared/racket-toolchain/racket/bin/racket}"
RACO="${RACO:-$(dirname "$RACKET")/raco}"
python3 scripts/prepare-overlay.py
python3 tests/patcher-test.py
python3 tests/independent-patcher-test.py
python3 performance/test_harness.py
"$RACO" test tests/source-preservation.rkt tests/paint-test.rkt tool/tests.rkt tool/frame-chrome-tests.rkt tests/independent-appearance-test.rkt tests/independent-paint-test.rkt tests/independent-theme-bridge-test.rkt
"$RACKET" scripts/render-proof.rkt
"$RACKET" scripts/preflight.rkt
