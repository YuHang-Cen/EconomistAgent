import { ChevronRight, Redo2, RefreshCw, Trash2, Undo2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Segment } from "../types";

interface SegmentViewProps {
  selectedAuthorName: string;
  selectedBookTitle: string;
  selectedChapterTitle: string;
  segments: Segment[];
  onDeleteSegment: (segmentId: string) => Promise<void> | void;
  onUndo: () => void;
  onRedo: () => void;
  onRefresh: () => Promise<void> | void;
  historyIndex: number;
  historyLength: number;
}

export default function SegmentView({
  selectedAuthorName,
  selectedBookTitle,
  selectedChapterTitle,
  segments,
  onDeleteSegment,
  onUndo,
  onRedo,
  onRefresh,
  historyIndex,
  historyLength,
}: SegmentViewProps) {
  return (
    <div className="flex-1 bg-background overflow-y-auto px-12 py-10">
      <div className="flex justify-between items-end mb-12">
        <div>
          <nav className="text-[10px] uppercase tracking-widest text-secondary font-bold mb-2 flex items-center gap-2">
            <span>Segment</span> <ChevronRight className="w-2.5 h-2.5" />
            <span>{selectedAuthorName || "No Author"}</span> <ChevronRight className="w-2.5 h-2.5" />
            <span className="text-primary">{selectedBookTitle || "No Document"}</span>
            {selectedChapterTitle && (
              <>
                <ChevronRight className="w-2.5 h-2.5" />
                <span className="text-primary/70">{selectedChapterTitle}</span>
              </>
            )}
          </nav>
          <h1 className="text-5xl font-headline text-on-background font-bold tracking-tight max-w-7xl leading-tight">
            {selectedChapterTitle || "Chapter Segment"}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex bg-surface-container-low rounded-sm p-1">
            <button
              onClick={onUndo}
              disabled={historyIndex === 0}
              className="p-2 hover:bg-surface-container-high transition-colors rounded-sm disabled:opacity-30 disabled:cursor-not-allowed"
              title="Undo"
            >
              <Undo2 className="w-4 h-4" />
            </button>
            <button
              onClick={onRedo}
              disabled={historyIndex >= historyLength - 1}
              className="p-2 hover:bg-surface-container-high transition-colors rounded-sm disabled:opacity-30 disabled:cursor-not-allowed"
              title="Redo"
            >
              <Redo2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-4 space-y-8">
          <section className="bg-surface-container-low p-8 rounded-sm editorial-shadow">
            <h3 className="text-xs font-bold uppercase tracking-widest text-secondary mb-4">Current Book</h3>
            <h2 className="text-2xl font-headline font-bold text-on-background leading-tight">
              {selectedBookTitle || "No Document Selected"}
            </h2>
          </section>

          <section className="bg-surface-container-low p-8 rounded-sm editorial-shadow">
            <h3 className="text-xs font-bold uppercase tracking-widest text-secondary mb-6">Segment Metrics</h3>
            <div className="space-y-4 mb-8">
              <div className="flex justify-between items-center text-sm">
                <span className="text-secondary">Total Segments</span>
                <span className="font-semibold">{segments.length} blocks</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-secondary">Total Word Count</span>
                <span className="font-semibold">
                  {segments.reduce((acc, item) => acc + item.content.split(/\s+/).filter(Boolean).length, 0)} words
                </span>
              </div>
            </div>
            <button
              onClick={onRefresh}
              className="w-full border border-primary/20 text-primary py-3 rounded-sm text-sm font-bold hover:bg-primary/5 transition-all flex items-center justify-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh Segment
            </button>
          </section>
        </div>

        <div className="col-span-12 lg:col-span-8 max-h-[calc(100vh-18rem)] overflow-y-auto pl-6 pr-4 custom-scrollbar">
          <section className="space-y-6">
            <AnimatePresence mode="popLayout">
              {segments.map((segment, index) => (
                <motion.div
                  key={segment.segmentId}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="group relative bg-surface-container-low p-8 rounded-sm border border-transparent hover:border-outline-variant/30 transition-all editorial-shadow z-10"
                >
                  <div className="absolute -left-3 top-8 w-6 h-6 bg-surface-container-highest border border-outline-variant/20 rounded-full flex items-center justify-center text-[10px] font-bold text-secondary z-20 shadow-sm">
                    {index + 1}
                  </div>
                  <p className="font-headline text-lg leading-relaxed text-on-background/80 italic whitespace-pre-wrap">
                    {segment.content}
                  </p>
                  <div className="mt-6 pt-4 border-t border-outline-variant/10 flex justify-end items-center">
                    <button
                      onClick={() => onDeleteSegment(segment.segmentId)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-error/70 hover:text-error p-2 rounded-sm"
                      title="Delete Segment"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            {segments.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-secondary italic">
                <p>No segments available.</p>
                <button onClick={onRefresh} className="mt-4 text-primary font-bold hover:underline">
                  Refresh from backend
                </button>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
