import {
  Book,
  BookOpen,
  ChevronDown,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
  User,
} from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import type { Author, Chapter, Document } from "../types";

interface SegmentSidebarProps {
  authors: Author[];
  documentsByAuthor: Record<string, Document[]>;
  chaptersByDocument: Record<string, Chapter[]>;
  selectedAuthorId: string | null;
  selectedDocumentId: string | null;
  selectedChapterId: string | null;
  onExpandAuthor: (authorId: string) => void;
  onSelectAuthor: (authorId: string) => void;
  onSelectDocument: (authorId: string, documentId: string) => void;
  onSelectChapter: (authorId: string, documentId: string, chapterId: string) => void;
  onDeleteChapter: (authorId: string, documentId: string, chapterId: string) => Promise<void> | void;
}

export default function SegmentSidebar({
  authors,
  documentsByAuthor,
  chaptersByDocument,
  selectedAuthorId,
  selectedDocumentId,
  selectedChapterId,
  onExpandAuthor,
  onSelectAuthor,
  onSelectDocument,
  onSelectChapter,
  onDeleteChapter,
}: SegmentSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedAuthors, setExpandedAuthors] = useState<Set<string>>(new Set());
  const [expandedDocuments, setExpandedDocuments] = useState<Set<string>>(new Set());

  const authorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const author of authors) {
      map[author.authorId] = author.authorName;
    }
    return map;
  }, [authors]);

  function toggleAuthor(authorId: string) {
    if (isCollapsed) return;
    const next = new Set(expandedAuthors);
    if (next.has(authorId)) {
      next.delete(authorId);
    } else {
      next.add(authorId);
      onExpandAuthor(authorId);
    }
    setExpandedAuthors(next);
    onSelectAuthor(authorId);
  }

  function toggleDocument(documentId: string) {
    if (isCollapsed) return;
    const next = new Set(expandedDocuments);
    if (next.has(documentId)) {
      next.delete(documentId);
    } else {
      next.add(documentId);
    }
    setExpandedDocuments(next);
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
            const docs = documentsByAuthor[authorId] || [];
            return (
              <div key={authorId}>
                <div
                  onClick={() => toggleAuthor(authorId)}
                  className={`rounded-sm flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                    selectedAuthorId === authorId ? "text-on-background font-bold bg-white/50" : "text-secondary hover:bg-white/30"
                  } ${isCollapsed ? "justify-center px-0" : ""}`}
                >
                  {!isCollapsed &&
                    (expandedAuthors.has(authorId) ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    ))}
                  <User className={`w-4 h-4 ${selectedAuthorId === authorId ? "text-primary" : "text-primary/70"}`} />
                  {!isCollapsed && <span className="text-sm">{author.authorName}</span>}
                </div>

                {!isCollapsed && expandedAuthors.has(authorId) && (
                  <div className="ml-4 space-y-1">
                    {docs.length === 0 ? (
                      <div className="px-4 py-2 text-xs text-secondary italic">No documents</div>
                    ) : (
                      docs.map((document) => {
                        const chapters = chaptersByDocument[document.documentId] || [];
                        return (
                          <div key={document.documentId}>
                            <div
                              onClick={() => {
                                toggleDocument(document.documentId);
                                onSelectDocument(authorId, document.documentId);
                              }}
                              className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-all ${
                                selectedDocumentId === document.documentId
                                  ? "text-primary font-medium"
                                  : "text-secondary hover:translate-x-1"
                              }`}
                            >
                              {expandedDocuments.has(document.documentId) ? (
                                <ChevronDown className="w-4 h-4" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                              <BookOpen
                                className={`w-4 h-4 ${selectedDocumentId === document.documentId ? "text-primary" : "text-primary/70"}`}
                              />
                              <span className="text-sm truncate">{document.bookTitle}</span>
                            </div>

                            {expandedDocuments.has(document.documentId) && (
                              <div className="ml-8 space-y-1 border-l border-outline-variant/20">
                                {chapters.length === 0 ? (
                                  <div className="px-4 py-2 text-xs text-secondary italic">No chapters</div>
                                ) : (
                                  chapters.map((chapter) => (
                                    <div
                                      key={chapter.chapterId}
                                      onClick={() =>
                                        onSelectChapter(authorId, document.documentId, chapter.chapterId)
                                      }
                                      className={`group flex items-center justify-between px-4 py-2 cursor-pointer text-xs transition-all ${
                                        selectedChapterId === chapter.chapterId
                                          ? "text-primary font-semibold bg-primary/10 rounded-sm"
                                          : "text-secondary hover:text-primary hover:translate-x-1"
                                      }`}
                                    >
                                      <div className="flex items-center gap-3 truncate">
                                        <Book className="w-3 h-3 shrink-0" />
                                        <span className="truncate">{chapter.chapterTitle}</span>
                                      </div>
                                      <button
                                        onClick={async (event) => {
                                          event.stopPropagation();
                                          await onDeleteChapter(authorId, document.documentId, chapter.chapterId);
                                        }}
                                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-outline-variant hover:text-error shrink-0"
                                        title="Delete Chapter"
                                      >
                                        <Trash2 className="w-3 h-3" />
                                      </button>
                                    </div>
                                  ))
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

      {!isCollapsed && selectedAuthorId && (
        <div className="p-3 text-[10px] text-secondary border-t border-outline-variant/10">
          Current author: {authorNameById[selectedAuthorId] || selectedAuthorId}
        </div>
      )}
    </motion.aside>
  );
}
