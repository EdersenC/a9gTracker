from __future__ import annotations

import argparse

from .runtime_config import load_runtime_config
from .runtime_supervisor import RuntimeSupervisor


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashcam runtime supervisor")
    parser.add_argument(
        "--config",
        default="configs/runtime/default.yaml",
        help="Path to runtime config YAML",
    )
    args = parser.parse_args()

    config = load_runtime_config(args.config)
    RuntimeSupervisor(config).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
