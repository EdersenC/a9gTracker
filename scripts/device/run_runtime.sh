#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_PATH="${1:-${ROOT_DIR}/configs/runtime/default.yaml}"

exec python3 -m services.runtime.main --config "${CONFIG_PATH}"
