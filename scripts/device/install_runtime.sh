#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_ROOT="/opt/dashcam"
ETC_DIR="/etc/dashcam"
STATE_DIR="/var/lib/dashcam-runtime/state"
LOG_DIR="/var/log/dashcam-runtime"
UNIT_SRC="${ROOT_DIR}/deploy/rpi/dashcam-runtime.service"
UNIT_DEST="/etc/systemd/system/dashcam-runtime.service"

id -u dashcam >/dev/null 2>&1 || useradd --system --home "${INSTALL_ROOT}" --shell /usr/sbin/nologin dashcam
mkdir -p "${INSTALL_ROOT}" "${ETC_DIR}" "${STATE_DIR}" "${LOG_DIR}"

cp -a "${ROOT_DIR}/." "${INSTALL_ROOT}/"
cp "${ROOT_DIR}/configs/runtime/default.yaml" "${ETC_DIR}/runtime.yaml"
cp "${UNIT_SRC}" "${UNIT_DEST}"

chown -R dashcam:dashcam "${INSTALL_ROOT}" "${STATE_DIR}" "${LOG_DIR}"
chmod 0644 "${UNIT_DEST}" "${ETC_DIR}/runtime.yaml"

systemctl daemon-reload
systemctl enable dashcam-runtime
systemctl restart dashcam-runtime

echo "Installed dashcam runtime service."
echo "Check: systemctl status dashcam-runtime"
