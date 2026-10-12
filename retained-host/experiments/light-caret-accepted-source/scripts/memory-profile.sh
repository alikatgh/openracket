#!/bin/sh
set -eu
. "$(dirname "$0")/proof-env.sh"
cd "$ROOT"
case "${1:-}" in
  --status|--restore|--unlimited) [ "$#" -eq 1 ] ;;
  --set-mib) [ "$#" -eq 2 ] ;;
  *) echo 'Usage: scripts/memory-profile.sh --status | --set-mib N | --unlimited | --restore' >&2; exit 2 ;;
esac
exec "$RACKET" -A "$ADDON" -R "$COMPILED_ROOTS" "$ROOT/scripts/memory-profile.rkt" "$@"
