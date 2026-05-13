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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      MODE="smoke"
      shift
      ;;
    --scenario)
      SCENARIO_ID="$2"
      shift 2
      ;;
    --artifacts-dir)
      ARTIFACTS_DIR="$2"
      shift 2
      ;;
    --timeout)
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
RUN_LOG="${ARTIFACTS_DIR}/${SCENARIO_ID}.sitl.log"
RESULT_JSON="${ARTIFACTS_DIR}/${SCENARIO_ID}.sitl.json"

write_result_json() {
  local status="$1"
  local details="$2"
  cat > "${RESULT_JSON}" <<EOF
{
  "scenario_id": "${SCENARIO_ID}",
  "mode": "${MODE}",
  "status": "${status}",
  "details": "${details}",
  "log_path": "${RUN_LOG}"
}
EOF
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
