#!/bin/sh
# This adapter is private to this generated app, not a replacement installation.
set -eu
RESOURCES=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")" && pwd)
. "$RESOURCES/openracket-config.sh"
ADDON="$OPENRACKET_SOURCE/profile/.local/share/racket"
ROOTS="$OPENRACKET_SOURCE/profile/compiled-cache:"
if [ "$#" -ge 7 ] && [ "$1" = -A ] && [ "$2" = "$ADDON" ] && \
   [ "$3" = -R ] && [ "$4" = "$ROOTS" ] && \
   [ "$5" = -l ] && [ "$6" = drracket ] && [ "$7" = -- ]; then
  # Child tools and user programs see the original configured runtime, as with
  # the tested source launcher, rather than treating this private adapter as it.
  RACKET=$OPENRACKET_OFFICIAL_RACKET
  export RACKET
  exec "$RESOURCES/../MacOS/$OPENRACKET_NATIVE_NAME" "$@"
fi
# Version, system-type, package checks and --check still use console Racket.
exec "$OPENRACKET_OFFICIAL_RACKET" "$@"
