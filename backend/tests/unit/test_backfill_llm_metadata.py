from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from app.scripts.backfill_llm_metadata import (
    DEFAULT_API_BASE,
    DEFAULT_MODEL_NAME,
    backfill_llm_metadata,
)


def test_backfill_llm_metadata_adds_missing_fields_and_is_idempotent() -> None:
    storage_root = Path("storage") / "test_tmp" / f"backfill-llm-{uuid4()}"
    snapshots_dir = storage_root / "authors" / "author-1" / "snapshots" / "snapshot-1"
    answers_dir = storage_root / "authors" / "author-1" / "answers" / "job-1"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    try:
        (snapshots_dir / "method_analysis.json").write_text(
            json.dumps({"chunks": [], "errors": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (snapshots_dir / "main_skill.json").write_text(
            json.dumps(
                {"main_skills": [], "model_name": "custom-model"},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (snapshots_dir / "sub_skill.json").write_text(
            json.dumps({"sub_skills": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (snapshots_dir / "main_skills_md.json").write_text(
            json.dumps([{"section_id": "s1"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (snapshots_dir / "sub_skills_md.json").write_text(
            json.dumps([{"section_id": "s1", "api_base": "https://custom.base"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (answers_dir / "answer.json").write_text(
            json.dumps({"query": "q1"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        first = backfill_llm_metadata(storage_root=storage_root)
        assert first.scanned_files == 6
        assert first.updated_files == 6
        assert first.warnings == []

        method_analysis = json.loads((snapshots_dir / "method_analysis.json").read_text(encoding="utf-8"))
        assert method_analysis["model_name"] == DEFAULT_MODEL_NAME
        assert method_analysis["api_base"] == DEFAULT_API_BASE

        main_skill = json.loads((snapshots_dir / "main_skill.json").read_text(encoding="utf-8"))
        assert main_skill["model_name"] == "custom-model"
        assert main_skill["api_base"] == DEFAULT_API_BASE

        sub_skill = json.loads((snapshots_dir / "sub_skill.json").read_text(encoding="utf-8"))
        assert sub_skill["model_name"] == DEFAULT_MODEL_NAME
        assert sub_skill["api_base"] == DEFAULT_API_BASE

        main_md = json.loads((snapshots_dir / "main_skills_md.json").read_text(encoding="utf-8"))
        assert main_md[0]["model_name"] == DEFAULT_MODEL_NAME
        assert main_md[0]["api_base"] == DEFAULT_API_BASE

        sub_md = json.loads((snapshots_dir / "sub_skills_md.json").read_text(encoding="utf-8"))
        assert sub_md[0]["model_name"] == DEFAULT_MODEL_NAME
        assert sub_md[0]["api_base"] == "https://custom.base"

        answer = json.loads((answers_dir / "answer.json").read_text(encoding="utf-8"))
        assert answer["model_name"] == DEFAULT_MODEL_NAME
        assert answer["api_base"] == DEFAULT_API_BASE

        second = backfill_llm_metadata(storage_root=storage_root)
        assert second.scanned_files == 6
        assert second.updated_files == 0
        assert second.warnings == []
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)

