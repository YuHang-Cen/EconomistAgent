import type { Chapter, Document } from "./types";

export interface SkillOutputsLike {
  mainSkillJson: Record<string, unknown> | null;
  subSkillJson: Array<Record<string, unknown>> | Record<string, unknown> | null;
  mainSkillsMdJson: Array<Record<string, unknown>>;
  subSkillsMdJson: Array<Record<string, unknown>>;
}

export interface ResolvedMethodologySection {
  sectionId: string;
  documentId: string | null;
  bookTitle: string;
  chapterTitle: string;
  isResolved: boolean;
  isLegacyFallback: boolean;
}

function readOptionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function sectionTitleKey(value: string | null): string {
  return (value || "").trim().toLocaleLowerCase();
}

function readSourceContext(item: Record<string, unknown>): {
  documentId: string | null;
  bookTitle: string | null;
  chapterTitle: string | null;
} {
  const raw = item.source_context;
  const sourceContext = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    documentId:
      readOptionalString(item.document_id) ||
      readOptionalString(item.documentId) ||
      readOptionalString(sourceContext.document_id) ||
      readOptionalString(sourceContext.documentId) ||
      null,
    bookTitle:
      readOptionalString(item.book_title) ||
      readOptionalString(item.bookTitle) ||
      readOptionalString(sourceContext.book_title) ||
      readOptionalString(sourceContext.bookTitle) ||
      null,
    chapterTitle:
      readOptionalString(item.chapter_title) ||
      readOptionalString(item.chapterTitle) ||
      readOptionalString(sourceContext.chapter_title) ||
      readOptionalString(sourceContext.chapterTitle) ||
      null,
  };
}

function buildLibraryIndexes(documents: Document[], chaptersByDocument: Record<string, Chapter[]>) {
  const documentById = new Map<string, Document>();
  const chapterById = new Map<
    string,
    { documentId: string; bookTitle: string; chapterTitle: string }
  >();
  const documentsByBookTitle = new Map<string, Document[]>();
  const chapterContextsByTitle = new Map<
    string,
    Array<{ documentId: string; bookTitle: string; chapterTitle: string }>
  >();

  for (const document of documents) {
    documentById.set(document.documentId, document);
    const bookKey = sectionTitleKey(document.bookTitle);
    const bookDocs = documentsByBookTitle.get(bookKey) || [];
    bookDocs.push(document);
    documentsByBookTitle.set(bookKey, bookDocs);

    const chapters = chaptersByDocument[document.documentId] || [];
    for (const chapter of chapters) {
      const context = {
        documentId: document.documentId,
        bookTitle: document.bookTitle,
        chapterTitle: chapter.chapterTitle,
      };
      chapterById.set(chapter.chapterId, context);
      const titleKey = sectionTitleKey(chapter.chapterTitle);
      if (!titleKey) continue;
      const titleContexts = chapterContextsByTitle.get(titleKey) || [];
      titleContexts.push(context);
      chapterContextsByTitle.set(titleKey, titleContexts);
    }
  }

  return {
    documentById,
    chapterById,
    documentsByBookTitle,
    chapterContextsByTitle,
  };
}

function resolveDocumentIdFromSnapshot(
  snapshotBookTitle: string | null,
  snapshotChapterTitle: string | null,
  indexes: ReturnType<typeof buildLibraryIndexes>
): string | null {
  if (!snapshotBookTitle) return null;
  const matchedDocuments = indexes.documentsByBookTitle.get(sectionTitleKey(snapshotBookTitle)) || [];
  if (matchedDocuments.length === 1) return matchedDocuments[0].documentId;
  if (matchedDocuments.length <= 1 || !snapshotChapterTitle) return null;

  const targetChapterKey = sectionTitleKey(snapshotChapterTitle);
  const matchedByChapter = matchedDocuments.filter((document) =>
    (indexes.chapterContextsByTitle.get(targetChapterKey) || []).some(
      (context) => context.documentId === document.documentId
    )
  );
  return matchedByChapter.length === 1 ? matchedByChapter[0].documentId : null;
}

function resolveSkillSection(
  skill: Record<string, unknown>,
  indexes: ReturnType<typeof buildLibraryIndexes>
): ResolvedMethodologySection | null {
  const sectionId = readOptionalString(skill.section_id);
  if (!sectionId) return null;

  const sectionTitle = readOptionalString(skill.section_title);
  const snapshotSource = readSourceContext(skill);

  const directChapter = indexes.chapterById.get(sectionId);
  const titleMatches = sectionTitle
    ? indexes.chapterContextsByTitle.get(sectionTitleKey(sectionTitle)) || []
    : [];
  const uniqueTitleMatch = titleMatches.length === 1 ? titleMatches[0] : null;

  const snapshotDocumentId =
    snapshotSource.documentId ||
    resolveDocumentIdFromSnapshot(snapshotSource.bookTitle, snapshotSource.chapterTitle || sectionTitle, indexes);
  const snapshotDocument = snapshotDocumentId ? indexes.documentById.get(snapshotDocumentId) || null : null;

  const resolvedDocumentId =
    snapshotDocumentId ||
    directChapter?.documentId ||
    uniqueTitleMatch?.documentId ||
    null;
  const resolvedDocument = resolvedDocumentId
    ? indexes.documentById.get(resolvedDocumentId) || null
    : null;

  const resolvedBookTitle =
    snapshotSource.bookTitle ||
    snapshotDocument?.bookTitle ||
    resolvedDocument?.bookTitle ||
    directChapter?.bookTitle ||
    uniqueTitleMatch?.bookTitle ||
    "Legacy Snapshot";
  const resolvedChapterTitle =
    snapshotSource.chapterTitle ||
    sectionTitle ||
    directChapter?.chapterTitle ||
    uniqueTitleMatch?.chapterTitle ||
    sectionId;

  return {
    sectionId,
    documentId: resolvedDocumentId,
    bookTitle: resolvedBookTitle,
    chapterTitle: resolvedChapterTitle,
    isResolved: !!resolvedDocumentId,
    isLegacyFallback: !resolvedDocumentId,
  };
}

export function buildResolvedMethodologySections(
  outputs: SkillOutputsLike | null,
  documents: Document[],
  chaptersByDocument: Record<string, Chapter[]>
): ResolvedMethodologySection[] {
  if (!outputs) return [];
  const indexes = buildLibraryIndexes(documents, chaptersByDocument);
  const mainSkillList = outputs.mainSkillJson?.main_skills;
  const mainSkills = Array.isArray(mainSkillList)
    ? mainSkillList.filter(
        (item): item is Record<string, unknown> => !!item && typeof item === "object"
      )
    : [];
  const mdIndex = new Map<string, Record<string, unknown>>();
  for (const item of outputs.mainSkillsMdJson) {
    const sectionId = readOptionalString(item.section_id);
    if (!sectionId || mdIndex.has(sectionId)) continue;
    mdIndex.set(sectionId, item);
  }

  const seenSectionIds = new Set<string>();
  const resolved: ResolvedMethodologySection[] = [];
  const sources = mainSkills.length > 0 ? mainSkills : outputs.mainSkillsMdJson;
  for (const source of sources) {
    const sectionId = readOptionalString(source.section_id);
    if (!sectionId || seenSectionIds.has(sectionId)) continue;
    seenSectionIds.add(sectionId);
    const merged = { ...(mdIndex.get(sectionId) || {}), ...source };
    const resolvedSection = resolveSkillSection(merged, indexes);
    if (resolvedSection) {
      resolved.push(resolvedSection);
    }
  }
  return resolved;
}
