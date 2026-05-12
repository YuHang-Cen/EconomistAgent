"""    ?author_skills   ocument_reload   uthor_answer                       ?"""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import JobStatus, OutputType, Stage
from app.domain.language import normalize_author_language
from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
    PipelineJob,
)
from app.infra import storage
from app.infra.settings import get_settings
from app.services.analyze_method_chunks import run_analyze_method_chunks
from app.services.answer_with_skills import run_answer_with_skills
from app.services.extract_paragraphs import run_extract_paragraphs
from app.services.llm_utils import get_effective_model_config, model_config_override_scope
from app.services.main_skill import run_main_skill
from app.services.render import run_render
from app.services.select_skills import run_select_skills
from app.services.sub_skill import run_sub_skill
from sqlalchemy import select
from sqlalchemy.orm import Session

MAIN_SKILL_ID_PATTERN = re.compile(r"^main_skill_(\d+)$")


class PipelineCanceledError(RuntimeError):
    """                            ?"""


def _now_iso() -> str:
    """    ?UTC ISO 8601               ?"""
    return datetime.now(tz=UTC).isoformat()


def _parse_outputs(outputs_json: str) -> dict[str, Any]:
    """    ?outputs_json                      ?"""
    try:
        parsed = json.loads(outputs_json or "{}")
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def _read_uri_content(uri: str) -> Any:
    """    ?URI     ?JSON               ?"""
    path = storage.resolve_storage_uri(uri)
    if not path.exists():
        return None
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def _ensure_not_canceled(session: Session, job: PipelineJob) -> None:
    """                                 ?"""
    session.refresh(job, attribute_names=["status"])
    if job.status == JobStatus.CANCELED.value:
        raise PipelineCanceledError("job canceled")


def _persist_stage_progress(
    session: Session, job: PipelineJob, stage: Stage, progress: int
) -> None:
    """Persist stage updates immediately so polling APIs can observe live progress."""
    job.status = JobStatus.RUNNING.value
    job.current_stage = stage.value
    job.progress = progress
    job.updated_at = _now_iso()
    session.flush()
    session.commit()


def _load_author_segments(session: Session, author_id: str) -> list[dict[str, Any]]:
    """         ?active                         ?"""
    documents = session.execute(
        select(AuthorDocument).where(
            AuthorDocument.author_id == author_id,
            AuthorDocument.status == "active",
        )
    ).scalars()
    document_rows = list(documents)
    if not document_rows:
        return []
    document_ids = [item.document_id for item in document_rows]
    document_by_id = {item.document_id: item for item in document_rows}

    chapters = session.execute(
        select(DocumentChapter).where(
            DocumentChapter.document_id.in_(document_ids),
            DocumentChapter.is_deleted.is_(False),
        )
    ).scalars()
    chapter_by_id = {chapter.chapter_id: chapter for chapter in chapters}

    segments = session.execute(
        select(DocumentSegment).where(
            DocumentSegment.document_id.in_(document_ids),
            DocumentSegment.is_deleted.is_(False),
        )
    ).scalars()
    segment_rows = sorted(
        list(segments),
        key=lambda item: (item.document_id, item.chapter_id, item.order_index),
    )

    result: list[dict[str, Any]] = []
    for segment in segment_rows:
        chapter = chapter_by_id.get(segment.chapter_id)
        if chapter is None:
            continue
        result.append(
            {
                "document_id": segment.document_id,
                "book_title": str(getattr(document_by_id.get(segment.document_id), "book_title", "") or ""),
                "chapter_id": segment.chapter_id,
                "chapter_title": chapter.chapter_title,
                "chunk_id": segment.chunk_id,
                "content": segment.content,
                "order_index": segment.order_index,
            }
        )
    return result


def _safe_main_skills(main_skill_json: dict[str, Any]) -> list[dict[str, Any]]:
    main_skills = main_skill_json.get("main_skills", [])
    if not isinstance(main_skills, list):
        return []
    return [item for item in main_skills if isinstance(item, dict)]


def _safe_sub_skills(sub_skill_json: dict[str, Any]) -> list[dict[str, Any]]:
    sub_skills = sub_skill_json.get("sub_skills", [])
    if not isinstance(sub_skills, list):
        return []
    return [item for item in sub_skills if isinstance(item, dict)]


def _load_latest_snapshot(session: Session, author_id: str) -> AuthorSkillSnapshot | None:
    return (
        session.execute(
            select(AuthorSkillSnapshot)
            .where(
                AuthorSkillSnapshot.author_id == author_id,
                AuthorSkillSnapshot.is_latest.is_(True),
            )
            .order_by(AuthorSkillSnapshot.created_at.desc())
        )
        .scalars()
        .first()
    )


def _load_snapshot_skill_payloads(
    snapshot: AuthorSkillSnapshot,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    outputs = _parse_outputs(snapshot.outputs_json)
    main_skill_uri = outputs.get(OutputType.MAIN_SKILL_JSON.value)
    sub_skill_uri = outputs.get(OutputType.SUB_SKILL_JSON.value)
    main_skill_json = _read_uri_content(main_skill_uri) if isinstance(main_skill_uri, str) else None
    sub_skill_json = _read_uri_content(sub_skill_uri) if isinstance(sub_skill_uri, str) else None

    main_skills = (
        _safe_main_skills(main_skill_json)
        if isinstance(main_skill_json, dict)
        else []
    )
    sub_skills = (
        _safe_sub_skills(sub_skill_json)
        if isinstance(sub_skill_json, dict)
        else []
    )
    return main_skills, sub_skills


def _load_generated_section_history(session: Session, author_id: str) -> set[str]:
    latest_snapshot = _load_latest_snapshot(session=session, author_id=author_id)
    if latest_snapshot is None:
        return set()
    generated: set[str] = set()
    main_skills, _sub_skills = _load_snapshot_skill_payloads(latest_snapshot)
    for item in main_skills:
        section_id = str(item.get("section_id", "")).strip()
        if section_id:
            generated.add(section_id)
    return generated


def _collect_sections_from_segments(segments: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    section_contexts: dict[str, dict[str, str]] = {}
    for item in segments:
        section_id = str(item.get("chapter_id", "")).strip()
        if not section_id or section_id in section_contexts:
            continue
        section_contexts[section_id] = {
            "document_id": str(item.get("document_id", "")).strip() or section_id,
            "book_title": str(item.get("book_title", "")).strip(),
            "chapter_title": str(item.get("chapter_title", "")).strip(),
        }
    return section_contexts


def _normalize_section_context(
    document_id: str | None,
    book_title: str | None,
    chapter_title: str | None,
) -> dict[str, str]:
    context: dict[str, str] = {}
    normalized_document_id = str(document_id or "").strip()
    normalized_book_title = str(book_title or "").strip()
    normalized_chapter_title = str(chapter_title or "").strip()
    if normalized_document_id:
        context["document_id"] = normalized_document_id
    if normalized_book_title:
        context["book_title"] = normalized_book_title
    if normalized_chapter_title:
        context["chapter_title"] = normalized_chapter_title
    return context


def _section_title_key(value: str | None) -> str:
    return str(value or "").strip().casefold()


def _build_section_title_contexts(
    section_contexts: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    unique_contexts: dict[str, dict[str, str]] = {}
    duplicated_keys: set[str] = set()
    for context in section_contexts.values():
        title_key = _section_title_key(context.get("chapter_title"))
        if not title_key:
            continue
        if title_key in unique_contexts:
            duplicated_keys.add(title_key)
            continue
        unique_contexts[title_key] = context
    for duplicated_key in duplicated_keys:
        unique_contexts.pop(duplicated_key, None)
    return unique_contexts


def _extract_source_context_from_item(item: dict[str, Any]) -> dict[str, str]:
    source_context = item.get("source_context")
    if not isinstance(source_context, dict):
        source_context = {}
    return _normalize_section_context(
        str(item.get("document_id", "")).strip()
        or str(source_context.get("document_id") or source_context.get("documentId") or "").strip(),
        str(item.get("book_title", "")).strip()
        or str(source_context.get("book_title") or source_context.get("bookTitle") or "").strip(),
        str(item.get("chapter_title", "")).strip()
        or str(source_context.get("chapter_title") or source_context.get("chapterTitle") or "").strip(),
    )


def _merge_source_context_into_item(
    item: dict[str, Any],
    context: dict[str, str],
) -> dict[str, Any]:
    merged = dict(item)
    normalized = _normalize_section_context(
        context.get("document_id"),
        context.get("book_title"),
        context.get("chapter_title"),
    )
    if not normalized:
        merged.pop("document_id", None)
        merged.pop("book_title", None)
        merged.pop("chapter_title", None)
        merged.pop("source_context", None)
        return merged
    merged["document_id"] = normalized.get("document_id", "")
    merged["book_title"] = normalized.get("book_title", "")
    merged["chapter_title"] = normalized.get("chapter_title", "")
    merged["source_context"] = normalized
    return merged


def _resolve_source_context_for_item(
    item: dict[str, Any],
    *,
    section_contexts: dict[str, dict[str, str]],
    section_title_contexts: dict[str, dict[str, str]],
    preferred_context: dict[str, str] | None = None,
) -> dict[str, str]:
    explicit_context = _extract_source_context_from_item(item)
    if preferred_context:
        explicit_context = _normalize_section_context(
            explicit_context.get("document_id") or preferred_context.get("document_id"),
            explicit_context.get("book_title") or preferred_context.get("book_title"),
            explicit_context.get("chapter_title") or preferred_context.get("chapter_title"),
        )

    section_id = str(item.get("section_id", "")).strip()
    current_context = section_contexts.get(section_id, {})
    if current_context:
        explicit_context = _normalize_section_context(
            explicit_context.get("document_id") or current_context.get("document_id"),
            explicit_context.get("book_title") or current_context.get("book_title"),
            explicit_context.get("chapter_title") or current_context.get("chapter_title"),
        )
        if explicit_context.get("document_id"):
            return explicit_context

    section_title = (
        explicit_context.get("chapter_title")
        or str(item.get("section_title", "")).strip()
    )
    matched_title_context = section_title_contexts.get(_section_title_key(section_title), {})
    if matched_title_context:
        return _normalize_section_context(
            explicit_context.get("document_id") or matched_title_context.get("document_id"),
            explicit_context.get("book_title") or matched_title_context.get("book_title"),
            explicit_context.get("chapter_title") or matched_title_context.get("chapter_title"),
        )
    return explicit_context


def _enrich_main_skills_with_source_context(
    main_skills: list[dict[str, Any]],
    *,
    section_contexts: dict[str, dict[str, str]],
    section_title_contexts: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in main_skills:
        context = _resolve_source_context_for_item(
            item,
            section_contexts=section_contexts,
            section_title_contexts=section_title_contexts,
        )
        enriched.append(_merge_source_context_into_item(item, context))
    return enriched


def _build_main_skill_context_indexes(
    main_skills: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_section_id: dict[str, dict[str, str]] = {}
    by_main_skill_id: dict[str, dict[str, str]] = {}
    for item in main_skills:
        context = _extract_source_context_from_item(item)
        if not context:
            continue
        section_id = str(item.get("section_id", "")).strip()
        main_skill_id = str(item.get("main_skill_id", "")).strip()
        if section_id and section_id not in by_section_id:
            by_section_id[section_id] = context
        if main_skill_id and main_skill_id not in by_main_skill_id:
            by_main_skill_id[main_skill_id] = context
    return by_section_id, by_main_skill_id


def _enrich_linked_skill_items_with_source_context(
    items: list[dict[str, Any]],
    *,
    section_contexts: dict[str, dict[str, str]],
    section_title_contexts: dict[str, dict[str, str]],
    main_skill_context_by_section_id: dict[str, dict[str, str]],
    main_skill_context_by_main_skill_id: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        main_skill_id = str(item.get("main_skill_id", "")).strip()
        section_id = str(item.get("section_id", "")).strip()
        preferred_context = (
            main_skill_context_by_main_skill_id.get(main_skill_id)
            or main_skill_context_by_section_id.get(section_id)
        )
        context = _resolve_source_context_for_item(
            item,
            section_contexts=section_contexts,
            section_title_contexts=section_title_contexts,
            preferred_context=preferred_context,
        )
        enriched.append(_merge_source_context_into_item(item, context))
    return enriched


def _sample_sections_for_generation(
    remaining_section_ids: list[str],
    section_contexts: dict[str, dict[str, str]],
    batch_size: int,
) -> set[str]:
    if len(remaining_section_ids) <= batch_size:
        return set(remaining_section_ids)

    sections_by_document: dict[str, list[str]] = {}
    for section_id in remaining_section_ids:
        context = section_contexts.get(section_id, {})
        document_id = str(context.get("document_id", "")).strip() or section_id
        sections_by_document.setdefault(document_id, []).append(section_id)

    selected: list[str] = []
    document_ids = list(sections_by_document.keys())
    doc_pick_count = min(batch_size, len(document_ids))
    chosen_document_ids = (
        list(document_ids)
        if doc_pick_count >= len(document_ids)
        else random.sample(document_ids, doc_pick_count)
    )

    for document_id in chosen_document_ids:
        document_sections = sections_by_document.get(document_id, [])
        if not document_sections:
            continue
        chosen_section = (
            document_sections[0]
            if len(document_sections) == 1
            else random.sample(document_sections, 1)[0]
        )
        selected.append(chosen_section)

    if len(selected) < batch_size:
        leftovers = [section_id for section_id in remaining_section_ids if section_id not in selected]
        extra_count = min(batch_size - len(selected), len(leftovers))
        if extra_count > 0:
            extras = leftovers if extra_count >= len(leftovers) else random.sample(leftovers, extra_count)
            selected.extend(extras)

    return set(selected)


def _filter_segments_by_sections(
    segments: list[dict[str, Any]], selected_section_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        item
        for item in segments
        if str(item.get("chapter_id", "")).strip() in selected_section_ids
    ]


def _parse_main_skill_index(main_skill_id: str) -> int | None:
    matched = MAIN_SKILL_ID_PATTERN.match(main_skill_id)
    if matched is None:
        return None
    return int(matched.group(1))


def _assign_new_main_skill_ids(
    existing_main_skills: list[dict[str, Any]],
    new_main_skills: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    max_index = 0
    for item in existing_main_skills:
        main_skill_id = str(item.get("main_skill_id", "")).strip()
        parsed = _parse_main_skill_index(main_skill_id)
        if parsed is not None:
            max_index = max(max_index, parsed)

    mapping: dict[str, str] = {}
    rewritten: list[dict[str, Any]] = []
    for item in new_main_skills:
        copied = dict(item)
        old_main_skill_id = str(item.get("main_skill_id", "")).strip()
        max_index += 1
        new_main_skill_id = f"main_skill_{max_index:03d}"
        copied["main_skill_id"] = new_main_skill_id
        if old_main_skill_id:
            mapping[old_main_skill_id] = new_main_skill_id
        rewritten.append(copied)
    return rewritten, mapping


def _remap_sub_skill_main_ids(
    sub_skills: list[dict[str, Any]], main_skill_id_mapping: dict[str, str]
) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    for item in sub_skills:
        copied = dict(item)
        old_main_skill_id = str(item.get("main_skill_id", "")).strip()
        new_main_skill_id = main_skill_id_mapping.get(old_main_skill_id)
        if new_main_skill_id:
            copied["main_skill_id"] = new_main_skill_id
        rewritten.append(copied)
    return rewritten


def _confidence_value(item: dict[str, Any]) -> float:
    value = item.get("confidence", 0.0)
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _merge_and_trim_main_skills(
    existing_main_skills: list[dict[str, Any]],
    new_main_skills: list[dict[str, Any]],
    max_main_skills: int | None,
) -> list[dict[str, Any]]:
    annotated: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(existing_main_skills):
        annotated.append((0, index, item))
    for index, item in enumerate(new_main_skills):
        annotated.append((1, index, item))

    ranked = sorted(
        annotated,
        key=lambda pair: (-_confidence_value(pair[2]), pair[0], pair[1]),
    )
    if max_main_skills is None or max_main_skills <= 0:
        kept = ranked
    else:
        kept = ranked[:max_main_skills]
    return [item for _source_priority, _order_index, item in kept]


def _filter_sub_skills_by_main_ids(
    sub_skills: list[dict[str, Any]], allowed_main_skill_ids: set[str]
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in sub_skills:
        main_skill_id = str(item.get("main_skill_id", "")).strip()
        if main_skill_id and main_skill_id in allowed_main_skill_ids:
            filtered.append(item)
    return filtered


def _run_main_skill_without_drop(method_analysis: dict[str, Any], *, language: str) -> dict[str, Any]:
    try:
        return run_main_skill(
            method_analysis=method_analysis,
            language=language,
            drop_low_confidence=False,
        )
    except TypeError:
        # Compatibility path for monkeypatched test doubles without the new argument.
        return run_main_skill(method_analysis=method_analysis)


def _run_analyze_with_language(
    segments: list[dict[str, Any]],
    *,
    language: str,
) -> dict[str, Any]:
    try:
        return run_analyze_method_chunks(segments=segments, language=language)
    except TypeError:
        return run_analyze_method_chunks(segments=segments)


def _run_sub_skill_with_language(
    main_skill_json: dict[str, Any],
    method_analysis: dict[str, Any],
    *,
    language: str,
) -> dict[str, Any]:
    try:
        return run_sub_skill(
            main_skill_json=main_skill_json,
            method_analysis=method_analysis,
            language=language,
        )
    except TypeError:
        return run_sub_skill(
            main_skill_json=main_skill_json,
            method_analysis=method_analysis,
        )


def _run_render_with_language(
    main_skill_json: dict[str, Any],
    sub_skill_json: dict[str, Any],
    *,
    language: str,
) -> dict[str, Any]:
    try:
        return run_render(
            main_skill_json=main_skill_json,
            sub_skill_json=sub_skill_json,
            language=language,
        )
    except TypeError:
        return run_render(main_skill_json=main_skill_json, sub_skill_json=sub_skill_json)


def _run_select_skills_with_language(
    snapshot_outputs: dict[str, Any],
    query: str,
    *,
    language: str,
) -> dict[str, Any]:
    try:
        return run_select_skills(
            snapshot_outputs=snapshot_outputs,
            query=query,
            language=language,
        )
    except TypeError:
        return run_select_skills(snapshot_outputs=snapshot_outputs, query=query)


def _run_answer_with_skills_with_language(
    query: str,
    selected: dict[str, Any],
    snapshot_outputs: dict[str, Any],
    *,
    language: str,
) -> dict[str, Any]:
    try:
        return run_answer_with_skills(
            query=query,
            selected=selected,
            snapshot_outputs=snapshot_outputs,
            language=language,
        )
    except TypeError:
        return run_answer_with_skills(
            query=query,
            selected=selected,
            snapshot_outputs=snapshot_outputs,
        )


def _load_job_model_config(job: PipelineJob) -> dict[str, Any]:
    raw = getattr(job, "model_config_json", "{}")
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _store_author_skill_artifacts(
    author_id: str,
    snapshot_id: str,
    created_at: str,
    method_analysis: dict[str, Any],
    main_skill_json: dict[str, Any],
    sub_skill_json: dict[str, Any],
    llm_metadata: dict[str, str],
    rendered: dict[str, Any],
) -> dict[str, str]:
    """                         ?artifact_type -> uri ?"""
    snapshot_dir = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    model_name = str(llm_metadata.get("model_name", "")).strip()
    api_base = str(llm_metadata.get("api_base", "")).strip()
    snapshot_meta_uri = storage.write_json(
        snapshot_dir / "snapshot_meta.json",
        {
            "author_id": author_id,
            "snapshot_id": snapshot_id,
            "created_at": created_at,
        },
    )
    method_analysis_payload = dict(method_analysis)
    method_analysis_payload["model_name"] = model_name
    method_analysis_payload["api_base"] = api_base
    method_analysis_json_uri = storage.write_json(
        snapshot_dir / "method_analysis.json", method_analysis_payload
    )
    main_skill_payload = dict(main_skill_json)
    main_skill_payload["model_name"] = model_name
    main_skill_payload["api_base"] = api_base
    main_skill_json_uri = storage.write_json(snapshot_dir / "main_skill.json", main_skill_payload)
    sub_skill_payload = dict(sub_skill_json)
    sub_skill_payload["model_name"] = model_name
    sub_skill_payload["api_base"] = api_base
    sub_skill_json_uri = storage.write_json(snapshot_dir / "sub_skill.json", sub_skill_payload)
    main_skill_items = _safe_main_skills(main_skill_payload)
    sub_skill_items = _safe_sub_skills(sub_skill_payload)
    main_skill_by_id = {
        str(item.get("main_skill_id", "")).strip(): item
        for item in main_skill_items
        if str(item.get("main_skill_id", "")).strip()
    }
    main_skill_context_by_section_id, main_skill_context_by_main_skill_id = (
        _build_main_skill_context_indexes(main_skill_items)
    )
    sub_skill_by_key = {
        (
            str(item.get("main_skill_id", "")).strip(),
            str(item.get("section_id", "")).strip(),
            str(item.get("name", "")).strip() or str(item.get("skill_name", "")).strip(),
        ): item
        for item in sub_skill_items
        if isinstance(item, dict)
    }
    main_skill_files = rendered.get("main_skill_files", [])
    main_skills_md_records: list[dict[str, Any]] = []
    if isinstance(main_skill_files, list):
        for item in main_skill_files:
            if not isinstance(item, dict):
                continue
            main_skill_id = item.get("main_skill_id")
            section_id = item.get("section_id")
            section_title = item.get("section_title")
            name = item.get("name")
            file_name = item.get("file_name")
            markdown = item.get("markdown")
            if not all(
                isinstance(value, str)
                for value in [main_skill_id, section_id, section_title, name, file_name, markdown]
            ):
                continue
            source_item = main_skill_by_id.get(main_skill_id, {})
            source_context = _extract_source_context_from_item(source_item)
            main_skills_md_records.append(
                {
                    "main_skill_id": main_skill_id,
                    "section_id": section_id,
                    "section_title": section_title,
                    "name": name,
                    "file_name": file_name,
                    "markdown": markdown,
                    "document_id": source_context.get("document_id", ""),
                    "book_title": source_context.get("book_title", ""),
                    "chapter_title": source_context.get("chapter_title", ""),
                    "source_context": source_context,
                    "model_name": model_name,
                    "api_base": api_base,
                }
            )
    main_skills_md_json_uri = storage.write_json(
        snapshot_dir / "main_skills_md.json", main_skills_md_records
    )

    sub_skill_files = rendered.get("sub_skill_files", [])
    zip_files: list[tuple[str, str]] = []
    sub_skills_md_records: list[dict[str, Any]] = []
    if isinstance(sub_skill_files, list):
        for item in sub_skill_files:
            if not isinstance(item, dict):
                continue
            file_name = item.get("name")
            if not isinstance(file_name, str):
                file_name = item.get("file_name")
            markdown = item.get("content")
            if not isinstance(markdown, str):
                markdown = item.get("markdown")
            if isinstance(file_name, str) and isinstance(markdown, str):
                zip_files.append((file_name, markdown))

            main_skill_id = item.get("main_skill_id")
            section_id = item.get("section_id")
            skill_name = item.get("skill_name")
            normalized_pattern = item.get("normalized_pattern")
            if all(
                isinstance(value, str)
                for value in [main_skill_id, section_id, skill_name, normalized_pattern]
            ) and isinstance(file_name, str) and isinstance(markdown, str):
                source_item = sub_skill_by_key.get((main_skill_id, section_id, skill_name), {})
                source_context = _extract_source_context_from_item(source_item)
                if not source_context:
                    source_context = (
                        main_skill_context_by_main_skill_id.get(main_skill_id, {})
                        or main_skill_context_by_section_id.get(section_id, {})
                    )
                sub_skills_md_records.append(
                    {
                        "main_skill_id": main_skill_id,
                        "section_id": section_id,
                        "name": skill_name,
                        "normalized_pattern": normalized_pattern,
                        "file_name": file_name,
                        "markdown": markdown,
                        "document_id": source_context.get("document_id", ""),
                        "book_title": source_context.get("book_title", ""),
                        "chapter_title": source_context.get("chapter_title", ""),
                        "source_context": source_context,
                        "model_name": model_name,
                        "api_base": api_base,
                    }
                )
    sub_skills_md_zip_uri = storage.write_zip_from_files(
        snapshot_dir / "sub_skills_md.zip", zip_files
    )
    sub_skills_md_json_uri = storage.write_json(
        snapshot_dir / "sub_skills_md.json", sub_skills_md_records
    )

    return {
        "snapshot_meta_json": snapshot_meta_uri,
        OutputType.METHOD_ANALYSIS_JSON.value: method_analysis_json_uri,
        OutputType.MAIN_SKILL_JSON.value: main_skill_json_uri,
        OutputType.SUB_SKILL_JSON.value: sub_skill_json_uri,
        OutputType.MAIN_SKILLS_MD_JSON.value: main_skills_md_json_uri,
        OutputType.SUB_SKILLS_MD_ZIP.value: sub_skills_md_zip_uri,
        OutputType.SUB_SKILLS_MD_JSON.value: sub_skills_md_json_uri,
    }


def _store_answer_artifact(
    author_id: str, job_id: str, answer_json: dict[str, Any]
) -> dict[str, str]:
    """                           artifact_type -> uri ?"""
    answer_dir = storage.answer_root(author_id=author_id, job_id=job_id)
    answer_json_uri = storage.write_json(answer_dir / "answer.json", answer_json)
    return {OutputType.ANSWER_JSON.value: answer_json_uri}


def upgrade_snapshot_source_contexts(
    session: Session,
    *,
    author_id: str,
    outputs: dict[str, Any],
) -> bool:
    if not author_id:
        return False
    segments = _load_author_segments(session=session, author_id=author_id)
    if not segments:
        return False

    section_contexts = _collect_sections_from_segments(segments)
    if not section_contexts:
        return False
    section_title_contexts = _build_section_title_contexts(section_contexts)

    main_skill_uri = outputs.get(OutputType.MAIN_SKILL_JSON.value)
    if not isinstance(main_skill_uri, str):
        return False
    main_skill_path = storage.resolve_storage_uri(main_skill_uri)
    if not main_skill_path.exists():
        return False

    try:
        main_skill_payload = json.loads(main_skill_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(main_skill_payload, dict):
        return False

    main_skills = _safe_main_skills(main_skill_payload)
    enriched_main_skills = _enrich_main_skills_with_source_context(
        main_skills,
        section_contexts=section_contexts,
        section_title_contexts=section_title_contexts,
    )
    main_skill_payload["main_skills"] = enriched_main_skills

    changed = enriched_main_skills != main_skills
    main_skill_context_by_section_id, main_skill_context_by_main_skill_id = (
        _build_main_skill_context_indexes(enriched_main_skills)
    )

    sub_skill_uri = outputs.get(OutputType.SUB_SKILL_JSON.value)
    if isinstance(sub_skill_uri, str):
        sub_skill_path = storage.resolve_storage_uri(sub_skill_uri)
        if sub_skill_path.exists():
            try:
                sub_skill_payload = json.loads(sub_skill_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                sub_skill_payload = None
            if isinstance(sub_skill_payload, dict):
                sub_skills = _safe_sub_skills(sub_skill_payload)
                enriched_sub_skills = _enrich_linked_skill_items_with_source_context(
                    sub_skills,
                    section_contexts=section_contexts,
                    section_title_contexts=section_title_contexts,
                    main_skill_context_by_section_id=main_skill_context_by_section_id,
                    main_skill_context_by_main_skill_id=main_skill_context_by_main_skill_id,
                )
                if enriched_sub_skills != sub_skills:
                    sub_skill_payload["sub_skills"] = enriched_sub_skills
                    storage.write_json(sub_skill_path, sub_skill_payload)
                    changed = True

    main_md_uri = outputs.get(OutputType.MAIN_SKILLS_MD_JSON.value)
    if isinstance(main_md_uri, str):
        main_md_path = storage.resolve_storage_uri(main_md_uri)
        if main_md_path.exists():
            try:
                main_md_payload = json.loads(main_md_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                main_md_payload = None
            if isinstance(main_md_payload, list):
                main_md_items = [item for item in main_md_payload if isinstance(item, dict)]
                enriched_main_md_items = _enrich_linked_skill_items_with_source_context(
                    main_md_items,
                    section_contexts=section_contexts,
                    section_title_contexts=section_title_contexts,
                    main_skill_context_by_section_id=main_skill_context_by_section_id,
                    main_skill_context_by_main_skill_id=main_skill_context_by_main_skill_id,
                )
                if enriched_main_md_items != main_md_items:
                    storage.write_json(main_md_path, enriched_main_md_items)
                    changed = True

    sub_md_uri = outputs.get(OutputType.SUB_SKILLS_MD_JSON.value)
    if isinstance(sub_md_uri, str):
        sub_md_path = storage.resolve_storage_uri(sub_md_uri)
        if sub_md_path.exists():
            try:
                sub_md_payload = json.loads(sub_md_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                sub_md_payload = None
            if isinstance(sub_md_payload, list):
                sub_md_items = [item for item in sub_md_payload if isinstance(item, dict)]
                enriched_sub_md_items = _enrich_linked_skill_items_with_source_context(
                    sub_md_items,
                    section_contexts=section_contexts,
                    section_title_contexts=section_title_contexts,
                    main_skill_context_by_section_id=main_skill_context_by_section_id,
                    main_skill_context_by_main_skill_id=main_skill_context_by_main_skill_id,
                )
                if enriched_sub_md_items != sub_md_items:
                    storage.write_json(sub_md_path, enriched_sub_md_items)
                    changed = True

    if changed:
        storage.write_json(main_skill_path, main_skill_payload)
    return changed


def run_author_skills(session: Session, job: PipelineJob) -> None:
    """     author_skills           ?author_skill_snapshots ?"""
    author = session.get(Author, job.author_id)
    if author is None:
        raise ValueError("author not found for author_skills")
    author_language = normalize_author_language(getattr(author, "language", None))
    settings = get_settings()
    batch_size = max(1, int(getattr(settings, "skills_batch_size", 2)))
    raw_max_main_skills = getattr(settings, "skills_max_main_skills", 0)
    try:
        max_main_skills = int(raw_max_main_skills)
    except (TypeError, ValueError):
        max_main_skills = 0

    _persist_stage_progress(session=session, job=job, stage=Stage.ANALYZE, progress=35)
    _ensure_not_canceled(session, job)

    segments = _load_author_segments(session=session, author_id=job.author_id)
    if not segments:
        raise ValueError("no active segments found for author_skills")

    section_contexts = _collect_sections_from_segments(segments)
    if not section_contexts:
        raise ValueError("no available sections found for author_skills")
    section_title_contexts = _build_section_title_contexts(section_contexts)
    generated_history = _load_generated_section_history(session=session, author_id=job.author_id)
    remaining_section_ids = [
        section_id for section_id in section_contexts.keys() if section_id not in generated_history
    ]
    latest_snapshot = _load_latest_snapshot(session=session, author_id=job.author_id)

    if not remaining_section_ids:
        if latest_snapshot is None:
            raise ValueError("no latest snapshot found while no remaining sections")
        now = _now_iso()
        job.snapshot_id = latest_snapshot.snapshot_id
        job.outputs_json = latest_snapshot.outputs_json
        job.current_stage = Stage.RENDER.value
        job.status = JobStatus.SUCCESS.value
        job.progress = 100
        job.updated_at = now
        job.finished_at = now
        session.flush()
        session.commit()
        return

    selected_section_ids = _sample_sections_for_generation(
        remaining_section_ids=remaining_section_ids,
        section_contexts=section_contexts,
        batch_size=batch_size,
    )
    selected_segments = _filter_segments_by_sections(
        segments=segments, selected_section_ids=selected_section_ids
    )
    if not selected_segments:
        raise ValueError("no selected segments found for author_skills")

    model_config = _load_job_model_config(job)
    llm_metadata: dict[str, str] = {}
    with model_config_override_scope(model_config):
        effective_model_config = get_effective_model_config()
        llm_metadata = {
            "model_name": effective_model_config["model_name"],
            "api_base": effective_model_config["api_base"],
        }
        method_analysis = _run_analyze_with_language(
            segments=selected_segments,
            language=author_language,
        )

        _ensure_not_canceled(session, job)
        _persist_stage_progress(session=session, job=job, stage=Stage.MAIN_SKILL, progress=55)
        new_main_skill_json = _run_main_skill_without_drop(
            method_analysis=method_analysis,
            language=author_language,
        )
        new_main_skills = _safe_main_skills(new_main_skill_json)

        _ensure_not_canceled(session, job)
        _persist_stage_progress(session=session, job=job, stage=Stage.SUB_SKILL, progress=70)
        new_sub_skill_json = _run_sub_skill_with_language(
            main_skill_json={"main_skills": new_main_skills},
            method_analysis=method_analysis,
            language=author_language,
        )
        new_sub_skills = _safe_sub_skills(new_sub_skill_json)

    existing_main_skills: list[dict[str, Any]] = []
    existing_sub_skills: list[dict[str, Any]] = []
    if latest_snapshot is not None:
        existing_main_skills, existing_sub_skills = _load_snapshot_skill_payloads(latest_snapshot)
    existing_main_skills = _enrich_main_skills_with_source_context(
        existing_main_skills,
        section_contexts=section_contexts,
        section_title_contexts=section_title_contexts,
    )
    existing_main_context_by_section_id, existing_main_context_by_main_skill_id = (
        _build_main_skill_context_indexes(existing_main_skills)
    )
    existing_sub_skills = _enrich_linked_skill_items_with_source_context(
        existing_sub_skills,
        section_contexts=section_contexts,
        section_title_contexts=section_title_contexts,
        main_skill_context_by_section_id=existing_main_context_by_section_id,
        main_skill_context_by_main_skill_id=existing_main_context_by_main_skill_id,
    )

    remapped_new_main_skills, main_skill_id_mapping = _assign_new_main_skill_ids(
        existing_main_skills=existing_main_skills,
        new_main_skills=new_main_skills,
    )
    remapped_new_main_skills = _enrich_main_skills_with_source_context(
        remapped_new_main_skills,
        section_contexts=section_contexts,
        section_title_contexts=section_title_contexts,
    )
    remapped_new_sub_skills = _remap_sub_skill_main_ids(
        sub_skills=new_sub_skills,
        main_skill_id_mapping=main_skill_id_mapping,
    )
    new_main_context_by_section_id, new_main_context_by_main_skill_id = (
        _build_main_skill_context_indexes(remapped_new_main_skills)
    )
    remapped_new_sub_skills = _enrich_linked_skill_items_with_source_context(
        remapped_new_sub_skills,
        section_contexts=section_contexts,
        section_title_contexts=section_title_contexts,
        main_skill_context_by_section_id=new_main_context_by_section_id,
        main_skill_context_by_main_skill_id=new_main_context_by_main_skill_id,
    )

    merged_main_skills = _merge_and_trim_main_skills(
        existing_main_skills=existing_main_skills,
        new_main_skills=remapped_new_main_skills,
        max_main_skills=max_main_skills,
    )
    allowed_main_skill_ids = {
        str(item.get("main_skill_id", "")).strip()
        for item in merged_main_skills
        if str(item.get("main_skill_id", "")).strip()
    }
    merged_sub_skills = _filter_sub_skills_by_main_ids(
        sub_skills=[*existing_sub_skills, *remapped_new_sub_skills],
        allowed_main_skill_ids=allowed_main_skill_ids,
    )
    merged_main_skill_json = {"main_skills": merged_main_skills}
    merged_sub_skill_json = {"sub_skills": merged_sub_skills}

    _ensure_not_canceled(session, job)
    _persist_stage_progress(session=session, job=job, stage=Stage.RENDER, progress=85)
    rendered = _run_render_with_language(
        main_skill_json=merged_main_skill_json,
        sub_skill_json=merged_sub_skill_json,
        language=author_language,
    )

    _ensure_not_canceled(session, job)
    snapshot_id = str(uuid.uuid4())
    now = _now_iso()
    outputs = _store_author_skill_artifacts(
        author_id=job.author_id,
        snapshot_id=snapshot_id,
        created_at=now,
        method_analysis=method_analysis,
        main_skill_json=merged_main_skill_json,
        sub_skill_json=merged_sub_skill_json,
        llm_metadata=llm_metadata,
        rendered=rendered,
    )

    latest_snapshots = session.execute(
        select(AuthorSkillSnapshot).where(
            AuthorSkillSnapshot.author_id == job.author_id,
            AuthorSkillSnapshot.is_latest.is_(True),
        )
    ).scalars()
    for snapshot in latest_snapshots:
        snapshot.is_latest = False

    session.add(
        AuthorSkillSnapshot(
            snapshot_id=snapshot_id,
            author_id=job.author_id,
            is_latest=True,
            outputs_json=json.dumps(outputs),
            created_at=now,
        )
    )

    job.snapshot_id = snapshot_id
    job.outputs_json = json.dumps(outputs)
    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.updated_at = now
    job.finished_at = now
    session.flush()
    session.commit()


def run_author_answer(session: Session, job: PipelineJob) -> None:
    """     author_answer           ?answer_json ?"""
    if not job.query:
        raise ValueError("author_answer requires non-empty query")
    author = session.get(Author, job.author_id)
    if author is None:
        raise ValueError("author not found for author_answer")
    author_language = normalize_author_language(getattr(author, "language", None))

    latest_snapshot = (
        session.execute(
            select(AuthorSkillSnapshot)
            .where(
                AuthorSkillSnapshot.author_id == job.author_id,
                AuthorSkillSnapshot.is_latest.is_(True),
            )
            .order_by(AuthorSkillSnapshot.created_at.desc())
        )
        .scalars()
        .first()
    )
    if latest_snapshot is None:
        raise ValueError("no latest snapshot found for author_answer")

    snapshot_output_uris = _parse_outputs(latest_snapshot.outputs_json)
    main_skill_uri = snapshot_output_uris.get(OutputType.MAIN_SKILL_JSON.value)
    sub_skill_uri = snapshot_output_uris.get(OutputType.SUB_SKILL_JSON.value)
    if not isinstance(main_skill_uri, str) or not isinstance(sub_skill_uri, str):
        raise ValueError("snapshot outputs missing main/sub skill uri")

    main_skill_json = _read_uri_content(main_skill_uri)
    sub_skill_json = _read_uri_content(sub_skill_uri)
    if not isinstance(main_skill_json, dict) or not isinstance(sub_skill_json, dict):
        raise ValueError("snapshot artifacts unreadable")
    snapshot_outputs = {
        OutputType.MAIN_SKILL_JSON.value: main_skill_json,
        OutputType.SUB_SKILL_JSON.value: sub_skill_json,
    }
    main_skills_md_uri = snapshot_output_uris.get(OutputType.MAIN_SKILLS_MD_JSON.value)
    if isinstance(main_skills_md_uri, str):
        main_skills_md_json = _read_uri_content(main_skills_md_uri)
        if isinstance(main_skills_md_json, list):
            snapshot_outputs[OutputType.MAIN_SKILLS_MD_JSON.value] = main_skills_md_json
    sub_skills_md_uri = snapshot_output_uris.get(OutputType.SUB_SKILLS_MD_JSON.value)
    if isinstance(sub_skills_md_uri, str):
        sub_skills_md_json = _read_uri_content(sub_skills_md_uri)
        if isinstance(sub_skills_md_json, list):
            snapshot_outputs[OutputType.SUB_SKILLS_MD_JSON.value] = sub_skills_md_json

    job.status = JobStatus.RUNNING.value
    job.current_stage = Stage.SELECT_SKILLS.value
    job.progress = 40
    job.updated_at = _now_iso()
    session.flush()
    _ensure_not_canceled(session, job)

    model_config = _load_job_model_config(job)
    llm_metadata: dict[str, str] = {}
    with model_config_override_scope(model_config):
        effective_model_config = get_effective_model_config()
        llm_metadata = {
            "model_name": effective_model_config["model_name"],
            "api_base": effective_model_config["api_base"],
        }
        selection = _run_select_skills_with_language(
            snapshot_outputs=snapshot_outputs,
            query=job.query,
            language=author_language,
        )
        if not selection.get("selected_section_id"):
            raise ValueError("no available skill selected for author_answer")

        _ensure_not_canceled(session, job)
        job.current_stage = Stage.ANSWER.value
        job.updated_at = _now_iso()
        answer_json = _run_answer_with_skills_with_language(
            query=job.query,
            selected=selection,
            snapshot_outputs=snapshot_outputs,
            language=author_language,
        )
    generated_at = _now_iso()
    answer_json["generated_at"] = generated_at
    answer_json["model_name"] = llm_metadata.get("model_name", "")
    answer_json["api_base"] = llm_metadata.get("api_base", "")

    outputs = _store_answer_artifact(
        author_id=job.author_id, job_id=job.job_id, answer_json=answer_json
    )
    now = generated_at
    job.snapshot_id = latest_snapshot.snapshot_id
    job.outputs_json = json.dumps(outputs)
    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.updated_at = now
    job.finished_at = now


def _upsert_chapters_and_segments(
    session: Session, document_id: str, extracted_rows: list[dict[str, Any]]
) -> None:
    """     segment_sync          ?chunk_id                             ?"""
    existing_chapters = session.execute(
        select(DocumentChapter).where(DocumentChapter.document_id == document_id)
    ).scalars()
    chapter_by_title = {chapter.chapter_title: chapter for chapter in existing_chapters}

    skip_chapter_titles: set[str] = set()
    chapter_id_by_title: dict[str, str] = {}

    section_titles: list[str] = []
    for row in extracted_rows:
        section_title = str(row["section_title"])
        if section_title not in section_titles:
            section_titles.append(section_title)

    for order_index, section_title in enumerate(section_titles):
        existing = chapter_by_title.get(section_title)
        now = _now_iso()
        if existing:
            if existing.is_deleted:
                skip_chapter_titles.add(section_title)
                continue
            existing.order_index = order_index
            existing.updated_at = now
            chapter_id_by_title[section_title] = existing.chapter_id
            continue

        chapter = DocumentChapter(
            chapter_id=str(uuid.uuid4()),
            document_id=document_id,
            chapter_title=section_title,
            order_index=order_index,
            is_deleted=False,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(chapter)
        chapter_id_by_title[section_title] = chapter.chapter_id

    existing_segments = session.execute(
        select(DocumentSegment).where(DocumentSegment.document_id == document_id)
    ).scalars()
    segment_by_chunk = {segment.chunk_id: segment for segment in existing_segments}

    for row in extracted_rows:
        section_title = str(row["section_title"])
        if section_title in skip_chapter_titles:
            continue
        chapter_id = chapter_id_by_title.get(section_title)
        if not chapter_id:
            continue

        chunk_id = str(row["chunk_id"])
        content = str(row["content"])
        order_index = int(row["order_index"])
        existing_segment = segment_by_chunk.get(chunk_id)
        now = _now_iso()

        if existing_segment:
            if existing_segment.is_deleted:
                continue
            existing_segment.chapter_id = chapter_id
            existing_segment.content = content
            existing_segment.order_index = order_index
            existing_segment.updated_at = now
            continue

        session.add(
            DocumentSegment(
                segment_id=str(uuid.uuid4()),
                document_id=document_id,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                content=content,
                order_index=order_index,
                is_deleted=False,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )


def run_document_reload(session: Session, job: PipelineJob) -> None:
    """     document_reload         tract -> segment_sync ?"""
    if not job.document_id:
        raise ValueError("document_reload requires document_id")

    document = session.get(AuthorDocument, job.document_id)
    if document is None:
        raise ValueError("document not found for document_reload")

    now = _now_iso()
    job.status = JobStatus.RUNNING.value
    job.current_stage = Stage.EXTRACT.value
    job.progress = 60
    job.updated_at = now
    document.status = "processing"
    document.updated_at = now
    session.flush()
    _ensure_not_canceled(session, job)

    extracted_rows = run_extract_paragraphs(
        book_title=document.book_title, pdf_uri=document.pdf_uri
    )
    try:
        storage.write_json(
            storage.document_root(author_id=job.author_id, document_id=document.document_id)
            / "extracted_segments.json",
            extracted_rows,
        )
        storage.write_json(
            storage.document_root(author_id=job.author_id, document_id=document.document_id)
            / "document_meta.json",
            {
                "document_id": document.document_id,
                "author_id": job.author_id,
                "book_title": document.book_title,
                "pdf_uri": document.pdf_uri,
                "status": document.status,
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            },
        )
    except OSError:
        # Storage manifests are best-effort and should not fail the pipeline run.
        pass

    _ensure_not_canceled(session, job)
    job.current_stage = Stage.SEGMENT_SYNC.value
    job.updated_at = _now_iso()
    _upsert_chapters_and_segments(
        session=session,
        document_id=document.document_id,
        extracted_rows=extracted_rows,
    )

    report_uri = storage.write_json(
        storage.job_root(author_id=job.author_id, job_id=job.job_id)
        / "document_reload_report.json",
        {"segmentSyncRows": len(extracted_rows)},
    )
    now = _now_iso()
    job.status = JobStatus.SUCCESS.value
    job.progress = 100
    job.finished_at = now
    job.updated_at = now
    job.outputs_json = json.dumps({"document_reload_report": report_uri})
    document.status = "active"
    document.updated_at = now
    try:
        storage.write_json(
            storage.document_root(author_id=job.author_id, document_id=document.document_id)
            / "document_meta.json",
            {
                "document_id": document.document_id,
                "author_id": job.author_id,
                "book_title": document.book_title,
                "pdf_uri": document.pdf_uri,
                "status": document.status,
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            },
        )
    except OSError:
        pass
