#!/bin/sh
# Test-only entry, no user-profile discovery or initialization. Supervisor must
# provide exactly one existing, private, fresh test profile. No shell dotfiles.
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
fail() { printf '%s\n' "OpenRacket path probe: $1" >&2; exit 64; }
[ "$#" -eq 1 ] || fail 'expected one explicit test profile'
case "$1" in /*) ;; *) fail 'test profile must be absolute' ;; esac
[ -d "$1" ] && [ ! -L "$1" ] || fail 'test profile is missing or linked'
PROFILE=$(CDPATH= cd -- "$1" && pwd -P)
CONTENTS=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")/.." && pwd -P)
RESOURCES="$CONTENTS/Resources"
RUNTIME="$RESOURCES/runtime"
NATIVE="$CONTENTS/MacOS/ProbeNative"
for p in home tmp addons compiled; do
  [ -d "$PROFILE/$p" ] && [ ! -L "$PROFILE/$p" ] || fail 'test profile layout is invalid'
done
[ -f "$PROFILE/TEST-PROFILE" ] && [ ! -L "$PROFILE/TEST-PROFILE" ] || fail 'test profile marker missing'
[ ! -e "$PROFILE/result.json" ] && [ ! -L "$PROFILE/result.json" ] || fail 'test profile already used'
[ -x "$NATIVE" ] && [ ! -L "$NATIVE" ] || fail 'native launcher is missing or linked'
[ -x "$RUNTIME/bin/racket" ] || fail 'bundled console runtime is missing'
# env -i removes all PLT*, DYLD*, RACKET*, XDG*, shell-startup, and source-root
# overrides before native startup/imports. No source/build path is embedded.
# -E selects console runtime semantics; it does NOT claim to be the process image.
exec /usr/bin/env -i PATH="$PATH" HOME="$PROFILE/home" TMPDIR="$PROFILE/tmp" \
  LANG=en_US.UTF-8 RACKET="$RUNTIME/bin/racket" \
  "$NATIVE" -E "$RUNTIME/bin/racket" -X "$RUNTIME/collects" \
  -G "$RUNTIME/etc" -A "$PROFILE/addons" -U -R "$PROFILE/compiled" \
  -t "$RESOURCES/probe/boot.rkt" -- "$CONTENTS/.." "$PROFILE"
