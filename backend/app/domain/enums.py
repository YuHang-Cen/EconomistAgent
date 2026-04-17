"""定义任务状态、阶段与产物类型枚举。"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """定义任务生命周期状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


class JobType(StrEnum):
    """定义后端支持的任务类型。"""

    AUTHOR_SKILLS = "author_skills"
    DOCUMENT_RELOAD = "document_reload"
    AUTHOR_ANSWER = "author_answer"


class Stage(StrEnum):
    """定义流水线阶段标识。"""

    EXTRACT = "extract"
    SEGMENT_SYNC = "segment_sync"
    ANALYZE = "analyze"
    MAIN_SKILL = "main_skill"
    SUB_SKILL = "sub_skill"
    RENDER = "render"
    SELECT_SKILLS = "select_skills"
    ANSWER = "answer"


class OutputType(StrEnum):
    """定义对外产物类型枚举。"""

    MAIN_SKILL_JSON = "main_skill_json"
    SUB_SKILL_JSON = "sub_skill_json"
    METHOD_ANALYSIS_JSON = "method_analysis_json"
    ANSWER_JSON = "answer_json"
    MAIN_SKILL_MD = "main_skill_md"
    SUB_SKILLS_MD_ZIP = "sub_skills_md_zip"
