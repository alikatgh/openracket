#!/usr/bin/env bash
# Read-only live visibility check. No personal access token is needed.
set -euo pipefail
[[ ${GITHUB_REPOSITORY:-} == alikatgh/openracket ]] || { echo 'Wrong repository.' >&2; exit 1; }
[[ ${GITHUB_SERVER_URL:-} == https://github.com ]] || { echo 'Requires public GitHub.com.' >&2; exit 1; }
[[ ${GITHUB_EVENT_NAME:-} == workflow_dispatch ]] || { echo 'Manual runs only.' >&2; exit 1; }
[[ ${GITHUB_REF:-} == refs/heads/main ]] || { echo 'Dispatch the main branch only.' >&2; exit 1; }
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  'https://api.github.com/repos/alikatgh/openracket' |
  python3 -c 'import json,sys; r=json.load(sys.stdin); assert r.get("full_name")=="alikatgh/openracket" and r.get("private") is False and r.get("visibility")=="public", "Public repository required"'
