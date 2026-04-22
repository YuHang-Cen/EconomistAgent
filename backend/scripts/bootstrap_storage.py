"""Initialize runtime storage from demo_storage on first startup."""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    demo_storage = root / "demo_storage"
    runtime_storage = root / "storage"

    runtime_storage.mkdir(parents=True, exist_ok=True)

    if not demo_storage.exists():
        print("[bootstrap-storage] demo_storage not found, skipping initialization.")
        return 0

    if any(runtime_storage.iterdir()):
        print("[bootstrap-storage] runtime storage already initialized, skipping.")
        return 0

    shutil.copytree(demo_storage, runtime_storage, dirs_exist_ok=True)
    print("[bootstrap-storage] runtime storage initialized from demo_storage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
