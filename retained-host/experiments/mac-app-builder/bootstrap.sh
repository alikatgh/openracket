#!/bin/sh
# Candidate app entry point. No setup, package installation or shell-rc loading.
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
umask 077
CALLER_PWD=$PWD
CONTENTS=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")/.." && pwd)
RESOURCES="$CONTENTS/Resources"
fail() {
  printf '%s\n' "OpenRacket could not start: $1" >&2
  # Message is an AppleScript argument, never executable AppleScript text.
  /usr/bin/osascript "$RESOURCES/report-error.applescript" "$1" >/dev/null 2>&1 || :
  exit 1
}
[ -r "$RESOURCES/openracket-config.sh" ] || fail 'The app configuration is missing. Rebuild the preview app.'
# Reset only startup overrides before entering the tested launcher. The private
# dispatcher must not clear the launcher's subsequently established activations.
unset PLTCOLLECTS PLTCONFIGDIR PLTLINKS
unset PLT_COMPILED_FILE_CHECK PLT_ZO_PATH PLTDRDEBUG PLTDRCM PLTDRPAR
unset OPENRACKET_THEME OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD
unset OPENRACKET_UI OPENRACKET_HOST_THEME OPENRACKET_PROFILE
unset OPENRACKET_MEMORY_LIMIT_MIB
. "$RESOURCES/openracket-config.sh"
[ -x "$OPENRACKET_OFFICIAL_RACKET" ] || fail 'The configured Racket 9.3 executable is missing. Rebuild the app with its current location.'
[ -r "$OPENRACKET_SOURCE/scripts/launch-openracket.sh" ] || fail 'The configured preview source folder is missing. Restore it or rebuild the app.'
CURRENT_SOURCE=$(CDPATH= cd -- "$OPENRACKET_SOURCE" && pwd -P) || fail 'The preview source folder cannot be opened.'
[ "$CURRENT_SOURCE" = "$OPENRACKET_SOURCE" ] || fail 'The preview source folder now resolves somewhere else. Rebuild the app using its new location.'
[ -x "$CONTENTS/MacOS/$OPENRACKET_NATIVE_NAME" ] || fail 'The native launcher is missing. Rebuild this preview app.'
PROFILE="$OPENRACKET_SOURCE/profile"
[ -d "$PROFILE" ] || fail 'This preview has not been set up. Complete the separate source setup before creating or opening the app.'
for managed in "$PROFILE" "$PROFILE/.local" "$PROFILE/.local/share" \
               "$PROFILE/.local/share/racket" "$PROFILE/.cache" "$PROFILE/compiled-cache"; do
  [ ! -L "$managed" ] || fail 'A managed profile path is a symbolic link. The app will not use it.'
done
# A fresh, private log is under the existing profile, never in the application or
# original Racket installation. It can contain paths and runtime/program output;
# it stays private to this profile and is never uploaded automatically.
LOG=$(/usr/bin/mktemp "$PROFILE/openracket-app-launch.XXXXXX") || fail 'Cannot create a launch log in the preview profile.'
RACKET=$OPENRACKET_OFFICIAL_RACKET
export RACKET
if ! /bin/sh "$OPENRACKET_SOURCE/scripts/launch-openracket.sh" --check >"$LOG" 2>&1; then
  fail "The preview check failed. No package installation was attempted. See $LOG"
fi
# Finder file opens are Apple events handled by native DrRacket, not argv.
# Older Finder versions may supply a single leading process-serial-number flag.
if [ "$#" -gt 0 ] && printf '%s\n' "$1" | /usr/bin/grep -Eq '^-psn_[0-9]+_[0-9]+$'; then
  shift
fi
# Preserve argument boundaries and the caller's directory before the proven
# launcher changes directory. Absolute names also protect a file named --check.
for arg do
  [ -n "$arg" ] || fail 'An empty filename was supplied.'
  case "$arg" in
    /*) absolute=$arg ;;
    *) absolute="$CALLER_PWD/$arg" ;;
  esac
  set -- "$@" "$absolute"
  shift
done
RACKET="$RESOURCES/runtime-dispatch.sh"
export RACKET
# Keep the Launch Services process: no background child, supervisor or Terminal.
# Preflight failures have a dialog. Post-exec diagnostics remain in this log;
# native early-crash reporting is a separate acceptance gate.
exec /bin/sh "$OPENRACKET_SOURCE/scripts/launch-openracket.sh" "$@" >>"$LOG" 2>&1
