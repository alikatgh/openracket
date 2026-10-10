#!/usr/bin/env bash
# Official, checksum-pinned Minimal Racket for CI. No system-wide installation.
set -euo pipefail
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || {
  echo 'Requires an Apple Silicon macOS host.' >&2; exit 1;
}
: "${RUNNER_TEMP:?Set RUNNER_TEMP to an existing temporary working directory}"
url='https://download.racket-lang.org/releases/9.3/installers/racket-minimal-9.3-aarch64-macosx-cs.tgz'
sha256='93c498c54804945c53412395e9ec7b33c56834f541710c2b3e161182be0c2670'
work=$(mktemp -d "$RUNNER_TEMP/openracket-racket.XXXXXX")
archive="$work/racket.tgz"
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --retry 3 "$url" -o "$archive"
printf '%s  %s\n' "$sha256" "$archive" | shasum -a 256 -c -
tar -xzf "$archive" -C "$work"
racket="$work/racket/bin/racket"
[[ -x "$racket" ]] || { echo 'Unexpected official archive layout.' >&2; exit 1; }
[[ "$("$racket" -e '(display (version))')" == 9.3 ]]
[[ "$("$racket" -e "(display (system-type 'vm))")" == chez-scheme ]]
"$racket" -e '(require racket json racket/async-channel syntax/modread) (displayln "Required Racket modules available")'
if [[ -n ${GITHUB_ENV:-} ]]; then
  printf 'RACKET_BIN=%s\nRACKET_EXECUTABLE=%s\nRACKET=%s\n' "$racket" "$racket" "$racket" >> "$GITHUB_ENV"
fi
printf 'Racket ready at: %s\n' "$racket"
