import type { AnswerVM } from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asIsoDatetime(value: unknown): string | null {
  const text = asString(value);
  if (!text) return null;
  return Number.isNaN(Date.parse(text)) ? null : text;
}

function asNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is number => typeof item === "number");
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function parseOptionalArticle(value: unknown): AnswerVM["directApiArticle"] {
  if (!isRecord(value)) return null;
  const markdown = asString(value.markdown) || "";
  if (!markdown) return null;
  const rawStatus = asString(value.status);
  const status =
    rawStatus === "generated" || rawStatus === "fallback" ? rawStatus : "unknown";
  return {
    status,
    errorCode: asString(value.errorCode ?? value.error_code),
    title: asString(value.title) || "",
    markdown,
  };
}

export function parseMainSkillsMdJson(content: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(content)) {
    throw new Error("main_skills_md_json is not an array");
  }
  return content.filter(isRecord);
}

export function parseSubSkillsMdJson(content: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(content)) {
    throw new Error("sub_skills_md_json is not an array");
  }
  return content.filter(isRecord);
}

export function parseZipManifest(content: unknown): string[] {
  if (!isRecord(content)) {
    throw new Error("zip output content is invalid");
  }
  const files = content.files;
  if (!Array.isArray(files)) {
    return [];
  }
  return files.filter((item): item is string => typeof item === "string");
}

export function parseAnswerJson(content: unknown): AnswerVM {
  if (!isRecord(content)) {
    throw new Error("answer_json is not an object");
  }
  const answer = content.answer;
  if (!isRecord(answer)) {
    throw new Error("answer_json.answer is invalid");
  }

  const selectedSkillIndices = asNumberArray(
    content.selectedSkillIndices ?? content.selected_skill_indices
  );
  const selectedSectionIds = asStringArray(
    content.selectedSectionIds ?? content.selected_section_ids
  );
  const selectedMainSkillNames = asStringArray(
    content.selectedMainSkillNames ?? content.selected_main_skill_names
  );
  const selectedSubSkillNames = asStringArray(
    content.selectedSubSkillNames ?? content.selected_sub_skill_names
  );

  return {
    query: asString(content.query) || "",
    generatedAt: asIsoDatetime(content.generatedAt ?? content.generated_at),
    modelName: asString(content.modelName ?? content.model_name),
    apiBase: asString(content.apiBase ?? content.api_base),
    selectedSkillIndices,
    selectedSectionIds,
    selectedSkillIndex:
      typeof (content.selectedSkillIndex ?? content.selected_skill_index) === "number"
        ? (content.selectedSkillIndex ?? content.selected_skill_index) as number
        : null,
    selectedSectionId: asString(content.selectedSectionId ?? content.selected_section_id),
    selectedMainSkillNames,
    selectedMainSkillName: asString(
      content.selectedMainSkillName ?? content.selected_main_skill_name
    ),
    selectedSubSkillNames,
    selectionMode:
      asString(content.selectionMode ?? content.selection_mode) || "fallback_rule",
    selectionWarning: asString(content.selectionWarning ?? content.selection_warning),
    answer: {
      title: asString(answer.title) || "",
      topic: asString(answer.topic) || "",
      summary: asString(answer.summary) || "",
      markdown: asString(answer.markdown) || "",
    },
    directApiArticle: parseOptionalArticle(
      content.directApiArticle ?? content.direct_api_article
    ),
  };
}
