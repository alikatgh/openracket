#!/usr/bin/env bash
# Full official Racket includes the real stock DrRacket, GUI, teaching tools.
# Installs only into this GitHub runner's disposable temporary directory.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo 'CI-only installer'; exit 1; }
: "${RUNNER_TEMP:?}"
work=$(mktemp -d "$RUNNER_TEMP/openracket-full.XXXXXX")
case "$(uname -s)/$(uname -m)" in
  Linux/x86_64)
    file=racket-9.3-x86_64-linux-buster-cs.sh
    sha=30dc59d9b5af083eacf793253d35782c5231e8bfb7a7331fe32ccd9a41fd792f
    ;;
  Darwin/arm64)
    file=racket-9.3-aarch64-macosx-cs.dmg
    sha=404dcf7198eb8847bd357295a9f2659e427ab9d481d488a16c70d03db72d7b02
    ;;
  *) echo 'Only standard Ubuntu x64 / macOS Apple Silicon runners supported'; exit 1;;
esac
url="https://download.racket-lang.org/releases/9.3/installers/$file"
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --connect-timeout 30 --max-time 240 --retry 2 "$url" -o "$work/$file"
printf '%s  %s\n' "$sha" "$work/$file" | shasum -a 256 -c -
if [[ $(uname -s) == Linux ]]; then
  bash "$work/$file" --in-place --dest "$work/racket"
  root="$work/racket"
else
  mkdir "$work/mount"
  hdiutil attach "$work/$file" -readonly -nobrowse -mountpoint "$work/mount"
  trap 'hdiutil detach "$work/mount" || true' EXIT
  # Official DMG has one Racket directory; find it without assuming volume name.
  source_root=$(find "$work/mount" -maxdepth 3 -type f -path '*/bin/racket' -print | head -n 1)
  [[ -n "$source_root" ]] || { echo 'Official DMG layout changed'; exit 1; }
  source_root=$(dirname "$(dirname "$source_root")")
  ditto "$source_root" "$work/racket"
  hdiutil detach "$work/mount"
  trap - EXIT
  root="$work/racket"
fi
racket="$root/bin/racket"
[[ -x "$racket" && -x "$root/bin/raco" ]]
[[ $("$racket" -e '(display (version))') == 9.3 ]]
[[ $("$racket" -e "(display (system-type 'vm))") == chez-scheme ]]
"$racket" -e '(require setup/dirs) (printf "Full Racket ~a CS; drracket source: ~a\n" (version) (collection-file-path "drracket.rkt" "drracket"))'
printf 'RACKET=%s\nRACO=%s\nOPENRACKET_CI_INSTALL=%s\nPLTADDONDIR=%s\n' "$racket" "$root/bin/raco" "$root" "$RUNNER_TEMP/openracket-addon" >> "$GITHUB_ENV"
printf 'OPENRACKET_CI_STOCK_RACKET=%s\nOPENRACKET_CI_STOCK_ADDON=%s\n' "$racket" "$RUNNER_TEMP/openracket-stock-addon" >> "$GITHUB_ENV"
printf '%s\n' "$root/bin" >> "$GITHUB_PATH"
echo 'Verified official full Racket9.3 installer and version. All stock packages retained.'
