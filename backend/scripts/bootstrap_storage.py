"""Initialize runtime storage from demo_storage."""

from __future__ import annotations

import shutil
from pathlib import Path


def copy_missing_tree(source: Path, target: Path) -> tuple[int, int]:
    """Copy files that do not exist in the target tree, without overwriting runtime data."""
    copied_files = 0
    created_dirs = 0

    for source_path in source.rglob("*"):
        relative = source_path.relative_to(source)
        target_path = target / relative
        if source_path.is_dir():
            if not target_path.exists():
                target_path.mkdir(parents=True, exist_ok=True)
                created_dirs += 1
            continue

        if target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_files += 1

    return copied_files, created_dirs


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    demo_storage = root / "demo_storage"
    runtime_storage = root / "storage"

    runtime_storage.mkdir(parents=True, exist_ok=True)

    if not demo_storage.exists():
        print("[bootstrap-storage] demo_storage not found, skipping initialization.")
        return 0

    copied_files, created_dirs = copy_missing_tree(demo_storage, runtime_storage)
    if copied_files or created_dirs:
        print(
            "[bootstrap-storage] runtime storage synchronized from demo_storage "
            f"(copied_files={copied_files}, created_dirs={created_dirs})."
        )
    else:
        print("[bootstrap-storage] runtime storage already has demo files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
