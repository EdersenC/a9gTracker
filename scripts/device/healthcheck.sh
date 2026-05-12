#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="${1:-/var/lib/dashcam-runtime/state/runtime-state.json}"

if [[ ! -f "${STATE_FILE}" ]]; then
  echo "runtime state not found: ${STATE_FILE}"
  exit 1
fi

cat "${STATE_FILE}"
