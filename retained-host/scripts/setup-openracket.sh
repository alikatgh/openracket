#!/bin/sh
set -eu
. "$(dirname "$0")/proof-env.sh"
cd "$ROOT"
if [ "${1:-}" != --install ]; then
  echo 'Usage: scripts/setup-openracket.sh --install' >&2
  echo 'Downloads official 9.3 stock dependencies if missing, then prepares only this isolated profile.' >&2
  exit 2
fi
mkdir -p "$ADDON" "$XDG_CACHE_HOME"
run_raco pkg install --auto --batch --no-setup --skip-installed --scope user \
  --catalog https://download.racket-lang.org/releases/9.3/catalog/ drracket htdp-lib
# A full Racket distribution may provide gui-lib outside the isolated profile.
# In that case copy the complete installed package, never modify the distribution.
gui=$(run_racket -e '(require pkg/lib)(display (or (pkg-directory "openracket-gui-lib") (pkg-directory "gui-lib") ""))')
if [ -z "$gui" ]; then echo 'Official gui-lib is missing after installation.' >&2; exit 3; fi
case "$gui" in
  "$PROFILE"/*) ;;
  *)
    run_racket -e '(require file/sha1 racket/file)(define p (vector-ref (current-command-line-arguments) 0))(unless (equal? (bytes->hex-string (sha256-bytes (file->bytes (build-path p "mrlib/switchable-button.rkt")))) "532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de") (error "Installed gui-lib differs from the pinned official9.3 source"))' -- "$gui"
    run_raco pkg install --scope user --batch --no-setup --deps fail --copy --force \
      --name openracket-gui-lib "$gui"
    ;;
esac
run_racket scripts/apply-overlay.rkt
run_racket scripts/apply-autosave.rkt
run_raco pkg install --scope user --batch --no-setup --deps fail --skip-installed \
  --link --name openracket-appearance "$ROOT/tool"
# Register the tool/info-based palettes and compile only the local tool. No docs,
# launchers, foreign library installers, or original installation writes.
run_raco setup --avoid-main --no-docs --no-launcher --no-foreign-libs \
  --no-install --no-post-install --pkgs openracket-appearance
button=$(run_racket -e '(display (collection-file-path "switchable-button.rkt" "mrlib"))')
case "$button" in "$PROFILE"/*) ;; *) echo 'The active toolbar did not resolve to the isolated package.' >&2; exit 4;; esac
run_raco make "$button" "$ROOT/tool/tool.rkt"
run_racket scripts/preflight.rkt
printf '\nPrepared the retained DrRacket host. Launch with scripts/launch-openracket.sh.\n'
