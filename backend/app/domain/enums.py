"""Task statuses, stages, and output type enums."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Task lifecycle status."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


class JobType(StrEnum):
    """Supported pipeline job types."""

    AUTHOR_SKILLS = "author_skills"
    DOCUMENT_RELOAD = "document_reload"
    AUTHOR_ANSWER = "author_answer"


class Stage(StrEnum):
    """Pipeline stage identifiers."""

    EXTRACT = "extract"
    SEGMENT_SYNC = "segment_sync"
    ANALYZE = "analyze"
    MAIN_SKILL = "main_skill"
    SUB_SKILL = "sub_skill"
    RENDER = "render"
    SELECT_SKILLS = "select_skills"
    ANSWER = "answer"


class OutputType(StrEnum):
    """Public output artifact types."""

    MAIN_SKILL_JSON = "main_skill_json"
    SUB_SKILL_JSON = "sub_skill_json"
    METHOD_ANALYSIS_JSON = "method_analysis_json"
    ANSWER_JSON = "answer_json"
    MAIN_SKILL_MD = "main_skill_md"
    MAIN_SKILLS_MD_JSON = "main_skills_md_json"
    SUB_SKILLS_MD_ZIP = "sub_skills_md_zip"
    SUB_SKILLS_MD_JSON = "sub_skills_md_json"
