#!/usr/bin/env bash
# DORMANT HELPER. Running this publishes publicly and requires explicit approval.
# No persistent token is created; the authorized job supplies its GITHUB_TOKEN.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
[[ ${OPENRACKET_ALLOW_PUBLIC_RELEASE:-} == yes ]] || {
  echo 'Public release publication is disabled. Explicit approval is required.' >&2; exit 1;
}
bash scripts/macos/check-public-repo.sh
: "${GH_TOKEN:?Only an authorized workflow job may supply its ephemeral GITHUB_TOKEN}"
: "${GITHUB_SHA:?}"
: "${GITHUB_RUN_ID:?}"
: "${GITHUB_RUN_ATTEMPT:?}"
[[ "$GITHUB_SHA" =~ ^[a-f0-9]{40}$ && "$GITHUB_RUN_ID" =~ ^[0-9]+$ && "$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+$ ]]
[[ $(git rev-parse HEAD) == "$GITHUB_SHA" ]] || { echo 'Source commit mismatch.' >&2; exit 1; }
repo=alikatgh/openracket
tag="macos-preview-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
python3 scripts/macos/write-report.py
python3 - <<'PY'
from pathlib import Path
p = Path('qa/macos-run/status.tsv')
rows = [line.split('\t', 1) for line in p.read_text().splitlines()]
expected = {'frozen-core', 'format', 'clippy', 'rust-tests', 'real-racket-supervisor',
            'real-racket-application', 'bridge-python', 'adversarial-python', 'release-build'}
assert len(rows) == len(expected) and {k for k,v in rows} == expected
assert all(v == 'PASS' for k,v in rows), 'Cannot publish failed/incomplete checks'
PY
(cd dist/macos && shasum -a 256 -c SHA256SUMS.txt)
assets=(dist/macos/OpenRacket-macos-arm64-preview.zip dist/macos/SHA256SUMS.txt MACOS-TEST-REPORT.md)
for asset in "${assets[@]}"; do
  [[ -s "$asset" ]] || { echo "Missing asset: $asset" >&2; exit 1; }
  [[ $(stat -f %z "$asset") -lt 2147483648 ]] || { echo 'Release asset too large.' >&2; exit 1; }
done
# Unique tag, no --clobber, no overwriting existing releases. Upload to a draft first.
notes=$(mktemp)
verify=$(mktemp -d)
trap 'rm -f "$notes"; rm -rf "$verify"' EXIT
cat > "$notes" <<NOTES
Early Apple Silicon/macOS 15 development preview from commit $GITHUB_SHA.

Ad-hoc integrity signature only: no Developer ID identity or Apple notarization.
Gatekeeper may block downloaded launch. No bypass or security-setting change is included.
Racket 9.3 CS must be installed separately. Intel is not included.

Read MACOS-TEST-REPORT.md for actual native build/runtime results and remaining GUI checks.
This is the frozen plain-text core, not full default-DrRacket compatibility.
SHA256SUMS.txt verifies the ZIP.
NOTES
gh release create "$tag" "${assets[@]}" --repo "$repo" --target "$GITHUB_SHA" \
  --title "OpenRacket macOS development preview ($GITHUB_RUN_ID)" \
  --notes-file "$notes" --draft --prerelease --latest=false
# Verify the uploaded bytes while the release is still a draft.
gh release download "$tag" --repo "$repo" --dir "$verify"
for asset in "${assets[@]}"; do cmp "$asset" "$verify/$(basename "$asset")"; done
bash scripts/macos/check-public-repo.sh
# The only public-release transition. Do not run without publication authorization.
gh release edit "$tag" --repo "$repo" --draft=false --prerelease --latest=false
gh release view "$tag" --repo "$repo" --json url,isDraft,isPrerelease \
  --jq 'if (.isDraft == false and .isPrerelease == true) then .url else error("Unexpected release state") end'
