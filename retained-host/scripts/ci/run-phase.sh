#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
phase=${1:?Provide a validation phase}
case "$phase" in prepare|stock|overlay|modern|performance) ;; *) echo 'Unknown validation phase'; exit 1;; esac
if [[ ${RUNNER_OS:-} == Linux ]]; then
  exec xvfb-run -a -s '-screen 0 1280x900x24 -nolisten tcp' python3 scripts/ci/run-native.py "$phase"
elif [[ ${RUNNER_OS:-} == macOS ]]; then
  exec python3 scripts/ci/run-native.py "$phase"
else
  echo 'Only standard Linux/macOS runners supported'; exit 1
fi
