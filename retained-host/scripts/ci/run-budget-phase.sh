#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
phase=${1:?Explicit budget phase required}
case "$phase" in prepare|correctness|performance) ;; *) exit 1;; esac
if [[ ${RUNNER_OS:-} == Linux ]]; then
  exec xvfb-run -a -s '-screen 0 1280x900x24 -nolisten tcp' python3 scripts/ci/run-budget.py "$phase"
elif [[ ${RUNNER_OS:-} == macOS ]]; then
  exec python3 scripts/ci/run-budget.py "$phase"
else
  echo 'Only standard Linux/macOS runners supported'; exit 1
fi
