import type { AnswerVM } from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
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

  const selectedSubSkillNamesRaw =
    content.selectedSubSkillNames ?? content.selected_sub_skill_names;
  const selectedSubSkillNames = Array.isArray(selectedSubSkillNamesRaw)
    ? selectedSubSkillNamesRaw.filter((item): item is string => typeof item === "string")
    : [];

  return {
    query: asString(content.query) || "",
    selectedSkillIndex:
      typeof (content.selectedSkillIndex ?? content.selected_skill_index) === "number"
        ? (content.selectedSkillIndex ?? content.selected_skill_index) as number
        : null,
    selectedSectionId: asString(content.selectedSectionId ?? content.selected_section_id),
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
  };
}
