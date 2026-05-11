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
import type { Author, Document } from "../types";
import type { ResolvedMethodologySection } from "../methodologySource";

interface MethodologySidebarProps {
  authors: Author[];
  documentsByAuthor: Record<string, Document[]>;
  generatedSections: ResolvedMethodologySection[];
  selectedAuthorId: string | null;
  selectedSectionId: string | null;
  onExpandAuthor: (authorId: string) => void;
  onSelectAuthor: (authorId: string) => void;
  onSelectSection: (sectionId: string) => void;
}

export default function MethodologySidebar({
  authors,
  documentsByAuthor,
  generatedSections,
  selectedAuthorId,
  selectedSectionId,
  onExpandAuthor,
  onSelectAuthor,
  onSelectSection,
}: MethodologySidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedAuthors, setExpandedAuthors] = useState<Set<string>>(new Set());
  const [expandedDocuments, setExpandedDocuments] = useState<Set<string>>(new Set());

  const sectionsByDocumentId = useMemo(() => {
    const grouped: Record<string, ResolvedMethodologySection[]> = {};
    for (const item of generatedSections) {
      const key = item.documentId || "__legacy__";
      const bucket = grouped[key] || [];
      bucket.push(item);
      grouped[key] = bucket;
    }
    return grouped;
  }, [generatedSections]);

  const selectedBookKey = useMemo(() => {
    if (!selectedSectionId) return null;
    const matchedSection = generatedSections.find((item) => item.sectionId === selectedSectionId);
    if (!matchedSection) return null;
    return matchedSection.documentId || "__legacy__";
  }, [generatedSections, selectedSectionId]);

  useEffect(() => {
    if (!selectedAuthorId) return;
    setExpandedAuthors(new Set([selectedAuthorId]));
  }, [selectedAuthorId]);

  useEffect(() => {
    if (!selectedBookKey) return;
    setExpandedDocuments((prev) => {
      const next = new Set(prev);
      next.add(selectedBookKey);
      return next;
    });
  }, [selectedBookKey]);

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
            const authorSections = isAuthorSelected ? generatedSections : [];
            const unresolvedSections = authorSections.filter((item) => !item.documentId);

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
                        const skillChapters = sectionsByDocumentId[document.documentId] || [];
                        const isDocumentSelected = selectedBookKey === document.documentId;
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
                                    const isChapterSelected = selectedSectionId === chapter.sectionId;
                                    return (
                                      <button
                                        key={chapter.sectionId}
                                        onClick={() => onSelectSection(chapter.sectionId)}
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
                      }).concat(
                        unresolvedSections.length === 0
                          ? []
                          : [
                              <div key="__legacy__">
                                <div
                                  onClick={() => toggleDocument("__legacy__")}
                                  className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-all ${
                                    selectedBookKey === "__legacy__"
                                      ? "text-primary font-medium"
                                      : "text-secondary hover:translate-x-1"
                                  }`}
                                >
                                  {expandedDocuments.has("__legacy__") ? (
                                    <ChevronDown className="w-4 h-4" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4" />
                                  )}
                                  <BookOpen
                                    className={`w-4 h-4 ${
                                      selectedBookKey === "__legacy__" ? "text-primary" : "text-primary/70"
                                    }`}
                                  />
                                  <span className="text-sm truncate">Legacy Snapshot</span>
                                </div>

                                {expandedDocuments.has("__legacy__") && (
                                  <div className="ml-8 space-y-1 border-l border-outline-variant/20">
                                    {unresolvedSections.map((chapter) => {
                                      const isChapterSelected = selectedSectionId === chapter.sectionId;
                                      return (
                                        <button
                                          key={chapter.sectionId}
                                          onClick={() => onSelectSection(chapter.sectionId)}
                                          className={`flex w-full items-center gap-3 px-4 py-2 text-left text-xs transition-all ${
                                            isChapterSelected
                                              ? "text-primary font-semibold bg-primary/10 rounded-sm"
                                              : "text-secondary hover:text-primary hover:translate-x-1"
                                          }`}
                                        >
                                          <span className="truncate">{chapter.chapterTitle}</span>
                                        </button>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>,
                            ]
                      )
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
