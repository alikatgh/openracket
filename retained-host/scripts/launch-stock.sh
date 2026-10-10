#!/bin/sh
set -eu
. "$(dirname "$0")/proof-env.sh"
cd "$ROOT"
# Share unchanged stock packages, use the patch's original paint/metrics branch,
# and keep stock-comparison preferences separate from the modern profile.
export PLTUSERHOME="$ROOT/profile-stock-preferences"
export OPENRACKET_UI=stock
unset OPENRACKET_HOST_THEME
exec "$RACKET" -A "$ADDON" -l drracket -- "$@"
