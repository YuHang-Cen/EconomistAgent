"""Backfill model_name/api_base into existing snapshot/answer JSON artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.infra import storage

DEFAULT_MODEL_NAME = "deepseek-chat"
DEFAULT_API_BASE = "https://api.deepseek.com"

SNAPSHOT_DICT_FILES = {
    "method_analysis.json",
    "main_skill.json",
    "sub_skill.json",
    "main_skill_md.json",
    "sub_skill_md.json",
}
SNAPSHOT_LIST_FILES = {
    "main_skills_md.json",
    "sub_skills_md.json",
}


@dataclass(frozen=True)
class BackfillSummary:
    scanned_files: int
    updated_files: int
    warnings: list[str]


def _safe_load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _safe_write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _setdefault_llm_metadata_on_dict(
    payload: dict[str, Any], *, model_name: str, api_base: str
) -> bool:
    changed = False
    if "model_name" not in payload:
        payload["model_name"] = model_name
        changed = True
    if "api_base" not in payload:
        payload["api_base"] = api_base
        changed = True
    return changed


def _setdefault_llm_metadata_on_list_items(
    payload: list[Any], *, model_name: str, api_base: str
) -> bool:
    changed = False
    for item in payload:
        if not isinstance(item, dict):
            continue
        if "model_name" not in item:
            item["model_name"] = model_name
            changed = True
        if "api_base" not in item:
            item["api_base"] = api_base
            changed = True
    return changed


def _apply_backfill_to_json_file(
    path: Path,
    *,
    model_name: str,
    api_base: str,
    list_payload_allowed: bool,
) -> tuple[bool, str | None]:
    payload = _safe_load_json(path)
    if payload is None:
        return False, f"invalid json: {path}"

    changed = False
    if isinstance(payload, dict):
        changed = _setdefault_llm_metadata_on_dict(
            payload, model_name=model_name, api_base=api_base
        )
    elif isinstance(payload, list) and list_payload_allowed:
        changed = _setdefault_llm_metadata_on_list_items(
            payload, model_name=model_name, api_base=api_base
        )
    else:
        return False, f"unsupported payload shape: {path}"

    if changed:
        _safe_write_json(path, payload)
    return changed, None


def backfill_llm_metadata(
    storage_root: Path,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    api_base: str = DEFAULT_API_BASE,
) -> BackfillSummary:
    warnings: list[str] = []
    scanned_files = 0
    updated_files = 0

    authors_dir = storage_root / "authors"
    if not authors_dir.exists() or not authors_dir.is_dir():
        return BackfillSummary(
            scanned_files=0,
            updated_files=0,
            warnings=[f"authors dir not found or not directory: {authors_dir}"],
        )

    for author_dir in sorted([p for p in authors_dir.iterdir() if p.is_dir()]):
        snapshots_dir = author_dir / "snapshots"
        if snapshots_dir.exists() and snapshots_dir.is_dir():
            for snapshot_dir in sorted([p for p in snapshots_dir.iterdir() if p.is_dir()]):
                for filename in sorted(SNAPSHOT_DICT_FILES | SNAPSHOT_LIST_FILES):
                    path = snapshot_dir / filename
                    if not path.exists() or not path.is_file():
                        continue
                    scanned_files += 1
                    changed, warning = _apply_backfill_to_json_file(
                        path,
                        model_name=model_name,
                        api_base=api_base,
                        list_payload_allowed=filename in SNAPSHOT_LIST_FILES,
                    )
                    if warning:
                        warnings.append(warning)
                        continue
                    if changed:
                        updated_files += 1

        answers_dir = author_dir / "answers"
        if answers_dir.exists() and answers_dir.is_dir():
            for answer_dir in sorted([p for p in answers_dir.iterdir() if p.is_dir()]):
                answer_json_path = answer_dir / "answer.json"
                if not answer_json_path.exists() or not answer_json_path.is_file():
                    continue
                scanned_files += 1
                changed, warning = _apply_backfill_to_json_file(
                    answer_json_path,
                    model_name=model_name,
                    api_base=api_base,
                    list_payload_allowed=False,
                )
                if warning:
                    warnings.append(warning)
                    continue
                if changed:
                    updated_files += 1

    return BackfillSummary(
        scanned_files=scanned_files,
        updated_files=updated_files,
        warnings=warnings,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill model_name/api_base fields into JSON artifacts."
    )
    parser.add_argument(
        "--storage-root",
        default="",
        help="Storage root directory (defaults to settings.storage_root).",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help=f"Default model_name used for missing fields (default: {DEFAULT_MODEL_NAME}).",
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"Default api_base used for missing fields (default: {DEFAULT_API_BASE}).",
    )
    args = parser.parse_args(argv)

    if args.storage_root:
        storage_root = Path(args.storage_root)
    else:
        storage_root = storage.ensure_storage_root()

    summary = backfill_llm_metadata(
        storage_root=storage_root,
        model_name=str(args.model_name),
        api_base=str(args.api_base),
    )
    print(
        json.dumps(
            {
                "scanned_files": summary.scanned_files,
                "updated_files": summary.updated_files,
                "warnings": summary.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

