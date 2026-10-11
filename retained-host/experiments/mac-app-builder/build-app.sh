#!/bin/sh
# One-time builder entry. Uses only the explicitly selected full Racket and macOS
# system shell; sanitation happens BEFORE any Racket collection is resolved.
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
umask 077
unset PLTCOLLECTS PLTCONFIGDIR PLTLINKS
unset PLT_COMPILED_FILE_CHECK PLT_ZO_PATH PLTDRDEBUG PLTDRCM PLTDRPAR
unset PLTCOMPILEDROOTS PLTADDONDIR PLTUSERHOME XDG_CACHE_HOME
fail() { printf '%s\n' "OpenRacket app build stopped: $1" >&2; exit 1; }
SOURCE= RACKET= RUNTIME_ROOT= OUTPUT=
# Keep the original argv intact. Racket's command-line parser checks duplicates,
# unknown options and the theme; this pass establishes safe startup locations.
need=
for arg do
  if [ -n "$need" ]; then
    case "$need" in
      --source) SOURCE=$arg;;
      --racket) RACKET=$arg;;
      --runtime-root) RUNTIME_ROOT=$arg;;
      --output) OUTPUT=$arg;;
    esac
    need=
  else
    case "$arg" in --source|--racket|--runtime-root|--output|--theme) need=$arg;; esac
  fi
done
[ -z "$need" ] || fail "Missing value for $need."
for value in "$SOURCE" "$RACKET" "$RUNTIME_ROOT" "$OUTPUT"; do
  case "$value" in /*) :;; *) fail 'Supply explicit absolute --source, --runtime-root, --racket and --output paths.';; esac
  # NUL cannot occur in an OS argument. Both LF and CR are forbidden.
  case "$value" in *'
'*|*''*) fail 'Configuration paths cannot contain line breaks.';; esac
done
case "$SOURCE" in *:*) fail 'The tested preview source path cannot contain a colon.';; esac
[ -d "$SOURCE/profile" ] || fail 'A separately prepared preview profile is required.'
for managed in "$SOURCE/profile" "$SOURCE/profile/.local" "$SOURCE/profile/.local/share" \
  "$SOURCE/profile/.local/share/racket" "$SOURCE/profile/.cache" "$SOURCE/profile/compiled-cache"; do
  [ ! -L "$managed" ] || fail 'A managed profile path is a symbolic link.'
done
[ -x "$RACKET" ] || fail 'The explicitly configured Racket executable is not executable.'
# The module independently checks all canonical boundaries, output exclusivity,
# the exact source manifest, official version/layout and query results before
# construction. Loading it does not install a compilation manager or any package.
PLTUSERHOME="$SOURCE/profile"
PLTADDONDIR="$SOURCE/profile/.local/share/racket"
PLTCOMPILEDROOTS="$SOURCE/profile/compiled-cache:"
XDG_CACHE_HOME="$SOURCE/profile/.cache"
export PLTUSERHOME PLTADDONDIR PLTCOMPILEDROOTS XDG_CACHE_HOME
HERE=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")" && pwd -P)
exec "$RACKET" -U -A "$PLTADDONDIR" -R "$PLTCOMPILEDROOTS" "$HERE/make-app.rkt" "$@"
