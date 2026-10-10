#!/bin/sh
set -eu
. "$(dirname "$0")/proof-env.sh"
cd "$ROOT"
export OPENRACKET_UI=modern
export OPENRACKET_HOST_THEME=1
# This adoption candidate uses the exact measured stock-save guard. Opt out with
# OPENRACKET_AUTOSAVE_GUARD=0; it does not enable any lexer/scan experiment.
case "${OPENRACKET_AUTOSAVE_GUARD:-1}" in
  1) export OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD=1 ;;
  0) unset OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD ;;
  *) echo 'OPENRACKET_AUTOSAVE_GUARD must be 0 or 1.' >&2; exit 2 ;;
esac
# Use the verified Cocoa adapter in this process only. Linux remains unchanged.
if [ -z "${OPENRACKET_NATIVE_APPEARANCE+x}" ]; then
  case $(run_racket -e '(display (system-type))') in
    macosx) export OPENRACKET_NATIVE_APPEARANCE=1 ;;
  esac
fi
if [ "${1:-}" = --check ]; then
  exec "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" "$ROOT/scripts/preflight.rkt"
fi
# Detect absent modules before attempting GUI startup; never substitute an evaluator.
run_racket -e '(require pkg/lib)(unless (and (pkg-directory "drracket") (pkg-directory "openracket-appearance")) (error "Run scripts/setup-openracket.sh --install in this isolated profile first"))'
# This is the original DrRacket entry point, with its real tools and default evaluator.
exec "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" -l drracket -- "$@"
