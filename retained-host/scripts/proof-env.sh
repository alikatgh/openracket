#!/bin/sh
# Sourced by launch/setup scripts; never modifies the caller's global environment.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROFILE="$ROOT/profile"
ADDON="$PROFILE/.local/share/racket"
if [ -z "${RACKET:-}" ]; then
  if command -v racket >/dev/null 2>&1; then RACKET=$(command -v racket)
  elif [ -x /workspace/shared/racket-toolchain/racket/bin/racket ]; then
    RACKET=/workspace/shared/racket-toolchain/racket/bin/racket
  else
    echo 'Set RACKET to the executable in your official Racket 9.3 installation.' >&2
    exit 2
  fi
fi
export PLTUSERHOME="$PROFILE"
export XDG_CACHE_HOME="$PROFILE/.cache"
export OPENRACKET_PROFILE="$PROFILE"
export RACKET
version=$("$RACKET" -e '(display (version))')
if [ "$version" != 9.3 ]; then
  echo "This source overlay is pinned to Racket 9.3; found $version. No changes made." >&2
  exit 2
fi
run_racket() { "$RACKET" -A "$ADDON" "$@"; }
run_raco() { run_racket -l raco -- "$@"; }
