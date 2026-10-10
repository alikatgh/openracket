#!/bin/sh
set -eu
. "$(dirname "$0")/proof-env.sh"
cd "$ROOT"
# Share unchanged stock packages, use the patch's original paint/metrics branch,
# and keep stock-comparison preferences separate from the modern profile.
export PLTUSERHOME="$ROOT/profile-stock-preferences"
export OPENRACKET_UI=stock
unset OPENRACKET_HOST_THEME OPENRACKET_NATIVE_APPEARANCE OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD
exec "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" -l drracket -- "$@"
