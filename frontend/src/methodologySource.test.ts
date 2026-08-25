import { strict as assert } from "node:assert";
import { test } from "node:test";

import type { Chapter, Document } from "./types";
import {
  buildResolvedMethodologySections,
  sortResolvedMethodologySections,
  type SkillOutputsLike,
} from "./methodologySource";

function outputs(mainSkills: Array<Record<string, unknown>>): SkillOutputsLike {
  return {
    mainSkillJson: { main_skills: mainSkills },
    subSkillJson: null,
    mainSkillsMdJson: [],
    subSkillsMdJson: [],
  };
}

function document(documentId: string, bookTitle: string): Document {
  return {
    documentId,
    authorId: "author-1",
    bookTitle,
    pdfUri: `memory://${documentId}.pdf`,
    documentKind: "book",
    status: "active",
  };
}

function chapter(
  chapterId: string,
  documentId: string,
  chapterTitle: string,
  orderIndex: number
): Chapter {
  return { chapterId, documentId, chapterTitle, orderIndex };
}

test("sorts confidence-shuffled sections by orderIndex and keeps zero first", () => {
  const documents = [document("doc-1", "Book One")];
  const chapters = {
    "doc-1": [
      chapter("chapter-c", "doc-1", "Chapter C", 2),
      chapter("chapter-a", "doc-1", "Chapter A", 0),
      chapter("chapter-b", "doc-1", "Chapter B", 1),
    ],
  };
  const resolved = buildResolvedMethodologySections(
    outputs([
      { section_id: "chapter-c", confidence: 0.9 },
      { section_id: "chapter-b", confidence: 0.8 },
      { section_id: "chapter-a", confidence: 0.1 },
    ]),
    documents,
    chapters
  );

  assert.deepEqual(
    sortResolvedMethodologySections(resolved).map((item) => [item.sectionId, item.orderIndex]),
    [
      ["chapter-a", 0],
      ["chapter-b", 1],
      ["chapter-c", 2],
    ]
  );
});

test("resolves identical chapter titles inside their own documents", () => {
  const documents = [document("doc-a", "Book A"), document("doc-b", "Book B")];
  const chapters = {
    "doc-a": [chapter("current-a", "doc-a", "Introduction", 4)],
    "doc-b": [chapter("current-b", "doc-b", "Introduction", 1)],
  };
  const resolved = buildResolvedMethodologySections(
    outputs([
      {
        section_id: "legacy-a",
        section_title: "Introduction",
        source_context: { document_id: "doc-a", chapter_title: "Introduction" },
      },
      {
        section_id: "legacy-b",
        section_title: "Introduction",
        source_context: { document_id: "doc-b", chapter_title: "Introduction" },
      },
    ]),
    documents,
    chapters
  );

  assert.deepEqual(
    resolved.map((item) => [item.documentId, item.orderIndex, item.isResolved]),
    [
      ["doc-a", 4, true],
      ["doc-b", 1, true],
    ]
  );
});

test("places unmatched legacy sections last with deterministic ties", () => {
  const documents = [document("doc-1", "Book One")];
  const chapters = {
    "doc-1": [chapter("current", "doc-1", "Current Chapter", 3)],
  };
  const resolved = buildResolvedMethodologySections(
    outputs([
      {
        section_id: "legacy-z",
        section_title: "Unknown Z",
        source_context: { document_id: "doc-1" },
      },
      { section_id: "current", section_title: "Current Chapter" },
      {
        section_id: "legacy-a",
        section_title: "Unknown A",
        source_context: { document_id: "doc-1" },
      },
    ]),
    documents,
    chapters
  );

  assert.deepEqual(
    sortResolvedMethodologySections(resolved).map((item) => [item.sectionId, item.orderIndex]),
    [
      ["current", 3],
      ["legacy-a", null],
      ["legacy-z", null],
    ]
  );
});
