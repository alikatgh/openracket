#!/bin/sh
set -eu
. "$(dirname "$0")/proof-env.sh"
cd "$ROOT"
export OPENRACKET_UI=modern
export OPENRACKET_HOST_THEME=1
if [ "${1:-}" = --check ]; then
  exec "$RACKET" -A "$ADDON" "$ROOT/scripts/preflight.rkt"
fi
# Detect absent modules before attempting GUI startup; never substitute an evaluator.
run_racket -e '(require pkg/lib)(unless (and (pkg-directory "drracket") (pkg-directory "openracket-appearance")) (error "Run scripts/setup-openracket.sh --install in this isolated profile first"))'
# This is the original DrRacket entry point, with its real tools and default evaluator.
exec "$RACKET" -A "$ADDON" -l drracket -- "$@"
