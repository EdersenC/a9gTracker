#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ARTIFACTS_DIR="${REPO_ROOT}/artifacts/sitl"
TIMEOUT_SECONDS="${PX4_SITL_TIMEOUT_SECONDS:-180}"
MODE="run"
SCENARIO_ID="smoke"

usage() {
  cat <<'EOF'
Usage: run_px4_sitl.sh [--smoke] [--scenario <id>] [--artifacts-dir <dir>] [--timeout <seconds>]

Modes:
  --smoke              Run harness smoke-check only (no PX4 requirement)
  --scenario <id>      Scenario identifier written into artifact metadata
  --artifacts-dir DIR  Output directory for SITL artifacts
  --timeout SEC        Timeout for real SITL command execution

Environment:
  PX4_SITL_CMD         Optional command to launch PX4 SITL in run mode
  PX4_SITL_TIMEOUT_SECONDS  Default timeout if --timeout is omitted
EOF
}

require_option_value() {
  local option_name="$1"
  if [[ $# -lt 2 || "${2:-}" == --* ]]; then
    echo "Missing value for ${option_name}" >&2
    usage >&2
    exit 2
  fi
}

sanitize_scenario_id() {
  local raw="$1"
  local safe
  safe="$(printf '%s' "${raw}" | tr -c 'A-Za-z0-9._-' '_')"
  safe="${safe#"${safe%%[!._-]*}"}"
  safe="${safe%"${safe##*[!._-]}"}"
  if [[ -z "${safe}" ]]; then
    echo "Invalid scenario id: ${raw}" >&2
    exit 2
  fi
  printf '%s' "${safe}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      MODE="smoke"
      shift
      ;;
    --scenario)
      require_option_value "$@"
      SCENARIO_ID="$2"
      shift 2
      ;;
    --artifacts-dir)
      require_option_value "$@"
      ARTIFACTS_DIR="$2"
      shift 2
      ;;
    --timeout)
      require_option_value "$@"
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "${ARTIFACTS_DIR}"
SAFE_SCENARIO_ID="$(sanitize_scenario_id "${SCENARIO_ID}")"
RUN_LOG="${ARTIFACTS_DIR}/${SAFE_SCENARIO_ID}.sitl.log"
RESULT_JSON="${ARTIFACTS_DIR}/${SAFE_SCENARIO_ID}.sitl.json"

write_result_json() {
  local status="$1"
  local details="$2"
  python3 - "${RESULT_JSON}" "${SCENARIO_ID}" "${MODE}" "${status}" "${details}" "${RUN_LOG}" <<'PY'
import json
import sys
from pathlib import Path

result_json, scenario_id, mode, status, details, run_log = sys.argv[1:]
payload = {
    "scenario_id": scenario_id,
    "mode": mode,
    "status": status,
    "details": details,
    "log_path": run_log,
}
Path(result_json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

if [[ "${MODE}" == "smoke" ]]; then
  {
    echo "[SITL] smoke mode"
    echo "[SITL] repo_root=${REPO_ROOT}"
    echo "[SITL] artifacts_dir=${ARTIFACTS_DIR}"
  } > "${RUN_LOG}"
  write_result_json "passed" "smoke-check completed"
  echo "PX4 SITL smoke check passed"
  exit 0
fi

if [[ -n "${PX4_SITL_CMD:-}" ]]; then
  echo "[SITL] Launching custom command: ${PX4_SITL_CMD}" | tee "${RUN_LOG}"
  if timeout "${TIMEOUT_SECONDS}" bash -lc "${PX4_SITL_CMD}" >> "${RUN_LOG}" 2>&1; then
    write_result_json "passed" "PX4 SITL command completed"
    exit 0
  fi
  write_result_json "failed" "PX4 SITL command failed"
  exit 1
fi

if command -v px4 >/dev/null 2>&1; then
  echo "[SITL] Found px4 binary; executing short health probe" | tee "${RUN_LOG}"
  if timeout "${TIMEOUT_SECONDS}" px4 --help >> "${RUN_LOG}" 2>&1; then
    write_result_json "passed" "px4 binary probe completed"
    exit 0
  fi
  write_result_json "failed" "px4 binary probe failed"
  exit 1
fi

{
  echo "[SITL] No PX4 binary and no PX4_SITL_CMD provided"
  echo "[SITL] Failing run mode; use --smoke or provide PX4_SITL_CMD"
} | tee "${RUN_LOG}"
write_result_json "failed" "PX4 runtime unavailable"
exit 1
