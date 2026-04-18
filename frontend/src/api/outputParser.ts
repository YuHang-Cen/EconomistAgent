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

  const selectedSubSkillNamesRaw = content.selectedSubSkillNames;
  const selectedSubSkillNames = Array.isArray(selectedSubSkillNamesRaw)
    ? selectedSubSkillNamesRaw.filter((item): item is string => typeof item === "string")
    : [];

  return {
    query: asString(content.query) || "",
    selectedSkillIndex:
      typeof content.selectedSkillIndex === "number"
        ? content.selectedSkillIndex
        : null,
    selectedSectionId: asString(content.selectedSectionId),
    selectedMainSkillName: asString(content.selectedMainSkillName),
    selectedSubSkillNames,
    selectionMode: asString(content.selectionMode) || "fallback_rule",
    selectionWarning: asString(content.selectionWarning),
    answer: {
      title: asString(answer.title) || "",
      topic: asString(answer.topic) || "",
      summary: asString(answer.summary) || "",
      markdown: asString(answer.markdown) || "",
    },
  };
}
