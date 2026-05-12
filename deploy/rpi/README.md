# Raspberry Pi Runtime Deployment

This deployment is fully offline and uses `systemd` for startup supervision.

## Files
- `dashcam-runtime.service`: service unit for runtime orchestration.
- `/etc/dashcam/runtime.yaml`: local runtime configuration.
- `/opt/dashcam`: project checkout used by runtime.

## Bring-up steps
1. Copy this repository to `/opt/dashcam`.
2. Run `scripts/device/install_runtime.sh` as root.
3. Validate with `systemctl status dashcam-runtime`.
4. Read health state from `/var/lib/dashcam-runtime/state/runtime-state.json`.

## Manufacturing reproducibility
- Install script creates deterministic user/group/paths.
- Service references fixed absolute paths.
- Runtime config is externalized in `/etc/dashcam/runtime.yaml` for local reconfiguration without code changes.
