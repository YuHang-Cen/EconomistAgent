import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  User,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import type { Author, Chapter, Document } from "../types";

interface MethodologySidebarProps {
  authors: Author[];
  documentsByAuthor: Record<string, Document[]>;
  chaptersByDocument: Record<string, Chapter[]>;
  generatedSectionIds: string[];
  selectedAuthorId: string | null;
  selectedSectionId: string | null;
  onExpandAuthor: (authorId: string) => void;
  onSelectAuthor: (authorId: string) => void;
  onSelectSection: (sectionId: string) => void;
}

export default function MethodologySidebar({
  authors,
  documentsByAuthor,
  chaptersByDocument,
  generatedSectionIds,
  selectedAuthorId,
  selectedSectionId,
  onExpandAuthor,
  onSelectAuthor,
  onSelectSection,
}: MethodologySidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedAuthors, setExpandedAuthors] = useState<Set<string>>(new Set());
  const [expandedDocuments, setExpandedDocuments] = useState<Set<string>>(new Set());

  const generatedSectionIdSet = useMemo(() => new Set(generatedSectionIds), [generatedSectionIds]);

  const selectedDocumentId = useMemo(() => {
    if (!selectedAuthorId || !selectedSectionId) return null;
    const documents = documentsByAuthor[selectedAuthorId] || [];
    for (const document of documents) {
      const chapters = chaptersByDocument[document.documentId] || [];
      if (chapters.some((chapter) => chapter.chapterId === selectedSectionId)) {
        return document.documentId;
      }
    }
    return null;
  }, [chaptersByDocument, documentsByAuthor, selectedAuthorId, selectedSectionId]);

  useEffect(() => {
    if (!selectedAuthorId) return;
    setExpandedAuthors(new Set([selectedAuthorId]));
  }, [selectedAuthorId]);

  useEffect(() => {
    if (!selectedDocumentId) return;
    setExpandedDocuments((prev) => {
      const next = new Set(prev);
      next.add(selectedDocumentId);
      return next;
    });
  }, [selectedDocumentId]);

  function toggleAuthor(authorId: string) {
    if (isCollapsed) return;
    setExpandedAuthors((prev) => {
      if (prev.has(authorId) && selectedAuthorId === authorId) {
        return new Set<string>();
      }
      return new Set([authorId]);
    });
    onExpandAuthor(authorId);
    onSelectAuthor(authorId);
  }

  function toggleDocument(documentId: string) {
    if (isCollapsed) return;
    setExpandedDocuments((prev) => {
      const next = new Set(prev);
      if (next.has(documentId)) {
        next.delete(documentId);
      } else {
        next.add(documentId);
      }
      return next;
    });
  }

  return (
    <motion.aside
      initial={false}
      animate={{ width: isCollapsed ? 64 : 320 }}
      className="bg-surface-container-low border-r border-outline-variant/10 flex flex-col shrink-0 overflow-hidden relative group"
    >
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className={`absolute right-4 top-4 z-20 p-2 hover:bg-surface-container-high rounded-sm text-secondary hover:text-primary transition-all duration-300 ${
          isCollapsed ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
        title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
      >
        {isCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
      </button>

      <div className={`flex-1 flex flex-col ${isCollapsed ? "items-center" : ""} overflow-y-auto custom-scrollbar`}>
        <nav className={`flex-1 px-4 space-y-1 ${isCollapsed ? "pt-16" : "pt-8"}`}>
          {authors.map((author) => {
            const authorId = author.authorId;
            const documents = documentsByAuthor[authorId] || [];
            const isAuthorSelected = selectedAuthorId === authorId;

            return (
              <div key={authorId}>
                <div
                  onClick={() => toggleAuthor(authorId)}
                  className={`rounded-sm flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                    isAuthorSelected ? "text-on-background font-bold bg-white/50" : "text-secondary hover:bg-white/30"
                  } ${isCollapsed ? "justify-center px-0" : ""}`}
                >
                  {!isCollapsed &&
                    (expandedAuthors.has(authorId) ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    ))}
                  <User className={`w-4 h-4 ${isAuthorSelected ? "text-primary" : "text-primary/70"}`} />
                  {!isCollapsed && <span className="text-sm">{author.authorName}</span>}
                </div>

                {!isCollapsed && expandedAuthors.has(authorId) && (
                  <div className="ml-4 space-y-1">
                    {documents.length === 0 ? (
                      <div className="px-4 py-2 text-xs text-secondary italic">No documents</div>
                    ) : (
                      documents.map((document) => {
                        const chapters = chaptersByDocument[document.documentId] || [];
                        const skillChapters = chapters.filter((chapter) =>
                          generatedSectionIdSet.has(chapter.chapterId)
                        );
                        const isDocumentSelected = selectedDocumentId === document.documentId;
                        const isExpanded = expandedDocuments.has(document.documentId);

                        return (
                          <div key={document.documentId}>
                            <div
                              onClick={() => toggleDocument(document.documentId)}
                              className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-all ${
                                isDocumentSelected
                                  ? "text-primary font-medium"
                                  : "text-secondary hover:translate-x-1"
                              }`}
                            >
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                              <BookOpen
                                className={`w-4 h-4 ${isDocumentSelected ? "text-primary" : "text-primary/70"}`}
                              />
                              <span className="text-sm truncate">{document.bookTitle}</span>
                            </div>

                            {isExpanded && (
                              <div className="ml-8 space-y-1 border-l border-outline-variant/20">
                                {skillChapters.length === 0 ? (
                                  <div className="px-4 py-2 text-xs text-secondary italic">
                                    No generated skills
                                  </div>
                                ) : (
                                  skillChapters.map((chapter) => {
                                    const isChapterSelected = selectedSectionId === chapter.chapterId;
                                    return (
                                      <button
                                        key={chapter.chapterId}
                                        onClick={() => onSelectSection(chapter.chapterId)}
                                        className={`flex w-full items-center gap-3 px-4 py-2 text-left text-xs transition-all ${
                                          isChapterSelected
                                            ? "text-primary font-semibold bg-primary/10 rounded-sm"
                                            : "text-secondary hover:text-primary hover:translate-x-1"
                                        }`}
                                      >
                                        <span className="truncate">{chapter.chapterTitle}</span>
                                      </button>
                                    );
                                  })
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </div>
    </motion.aside>
  );
}
