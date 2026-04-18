import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import type { Author, Job } from "../types";

interface AnalysisSidebarProps {
  authors: Author[];
  selectedAuthorId: string | null;
  selectedJobId: string | null;
  historyByAuthor: Record<string, Job[]>;
  loadingByAuthor: Record<string, boolean>;
  onExpandAuthor: (authorId: string) => void;
  onSelectAuthor: (authorId: string) => void;
  onSelectJob: (jobId: string) => void;
  onNewAnalysis: () => void;
}

export default function AnalysisSidebar({
  authors,
  selectedAuthorId,
  selectedJobId,
  historyByAuthor,
  loadingByAuthor,
  onExpandAuthor,
  onSelectAuthor,
  onSelectJob,
  onNewAnalysis,
}: AnalysisSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedAuthors, setExpandedAuthors] = useState<Set<string>>(new Set());

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

      <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar">
        <div className={`p-6 ${isCollapsed ? "pt-16 px-2" : ""}`}>
          <button
            onClick={onNewAnalysis}
            className={`w-full flex items-center justify-center gap-3 transition-colors py-4 px-6 rounded-sm border border-outline-variant/20 shadow-sm ${
              selectedJobId === null ? "bg-primary text-on-primary" : "bg-surface-container-highest hover:bg-surface-dim text-on-surface"
            } ${isCollapsed ? "px-0 w-10 h-10 mx-auto" : ""}`}
            title="New Analysis"
          >
            <Plus className={`w-4 h-4 shrink-0 ${selectedJobId === null ? "text-on-primary" : "text-primary"}`} />
            {!isCollapsed && (
              <span className="font-label text-xs font-bold uppercase tracking-widest">
                New Analysis
              </span>
            )}
          </button>
        </div>

        <div className={`flex-grow px-4 pb-8 ${isCollapsed ? "px-2" : ""}`}>
          <div className="space-y-4">
            {authors.map((author) => {
              const authorId = author.authorId;
              const jobs = historyByAuthor[authorId] || [];
              const loading = !!loadingByAuthor[authorId];
              const expanded = expandedAuthors.has(authorId);
              return (
                <div key={authorId} className="group">
                  <div
                    onClick={() => toggleAuthor(authorId)}
                    className={`flex items-center justify-between cursor-pointer py-2 px-2 hover:bg-surface-container transition-colors rounded-sm ${
                      isCollapsed ? "justify-center" : ""
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {!isCollapsed && (
                        expanded ? (
                          <ChevronDown className="w-4 h-4 text-secondary" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-secondary" />
                        )
                      )}
                      <div className="w-4 h-4 rounded-full bg-primary/10 flex items-center justify-center text-[8px] font-bold text-primary shrink-0">
                        {author.authorName.charAt(0)}
                      </div>
                      {!isCollapsed && (
                        <span
                          className={`font-label text-[10px] font-bold uppercase tracking-[0.15em] truncate ${
                            selectedAuthorId === authorId ? "text-primary" : "text-on-surface-variant"
                          }`}
                        >
                          {author.authorName}
                        </span>
                      )}
                    </div>
                    {!isCollapsed && (
                      <span className="font-label text-[9px] text-outline-variant px-1.5 py-0.5 border border-outline-variant/20 rounded">
                        {loading ? "..." : jobs.length}
                      </span>
                    )}
                  </div>

                  {!isCollapsed && expanded && (
                    <div className="space-y-1 pl-6 mt-2">
                      {loading && <div className="text-xs text-secondary px-2 py-1">Loading...</div>}
                      {!loading && jobs.length === 0 && (
                        <div className="text-xs text-secondary italic px-2 py-1">No analysis jobs yet.</div>
                      )}
                      {jobs.map((item) => (
                        <div
                          key={item.jobId}
                          onClick={() => onSelectJob(item.jobId)}
                          className={`group/item flex items-center justify-between p-2 rounded-sm cursor-pointer transition-all ${
                            selectedJobId === item.jobId
                              ? "border-l-2 border-primary bg-primary/5 text-primary font-medium"
                              : "hover:bg-surface-container-highest text-secondary"
                          }`}
                        >
                          <span className="font-body text-sm truncate pr-4">
                            {(item.query || "Untitled query").slice(0, 48)}
                          </span>
                          <span className="text-[10px] uppercase tracking-wider">{item.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </motion.aside>
  );
}
