import { ChevronRight, Undo2, Redo2, RefreshCw, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useCallback } from 'react';

const INITIAL_SEGMENTS = [
  {
    id: '01',
    title: 'Segment: Propensity to Exchange',
    content: 'This division of labour, from which so many advantages are derived, is not originally the effect of any human wisdom, which foresees and intends that general opulence to which it gives occasion. It is the necessary, though very slow and gradual consequence of a certain propensity in human nature which has in view no such extensive utility; the propensity to truck, barter, and exchange one thing for another.'
  },
  {
    id: '02',
    title: 'Segment: Human Uniqueness',
    content: 'Whether this propensity be one of those original principles in human nature of which no further account can be given; or whether, as seems more probable, it be the necessary consequence of the faculties of reason and speech, it belongs not to our present subject to inquire. It is common to all men, and to be found in no other race of animals, which seem to know neither this nor any other species of contracts.'
  },
  {
    id: '03',
    title: 'Segment: Self-Interest Principle',
    content: 'Man has almost constant occasion for the help of his brethren, and it is in vain for him to expect it from their benevolence only. He will be more likely to prevail if he can interest their self-love in his favour, and show them that it is for their own advantage to do for him what he requires of them.'
  },
  {
    id: '04',
    title: 'Segment: The Butcher\'s Interest',
    content: 'It is not from the benevolence of the butcher, the brewer, or the baker that we expect our dinner, but from their regard to their own interest. We address ourselves, not to their humanity but to their self-love, and never talk to them of our own necessities but of their advantages.'
  }
];

interface SegmentViewProps {
  selectedAuthor: string;
  selectedBook: string;
  selectedChapter: string;
  segments: { id: string; title: string; content: string }[];
  onDeleteSegment: (id: string) => void;
  onUndo: () => void;
  onRedo: () => void;
  onRefresh: () => void;
  historyIndex: number;
  historyLength: number;
}

export default function SegmentView({ 
  selectedAuthor, 
  selectedBook, 
  selectedChapter,
  segments,
  onDeleteSegment,
  onUndo,
  onRedo,
  onRefresh,
  historyIndex,
  historyLength
}: SegmentViewProps) {
  return (
    <div className="flex-1 bg-background overflow-y-auto px-12 py-10">
      {/* Header Section */}
      <div className="flex justify-between items-end mb-12">
        <div>
          <nav className="text-[10px] uppercase tracking-widest text-secondary font-bold mb-2 flex items-center gap-2">
            <span>Segment</span> <ChevronRight className="w-2.5 h-2.5" />
            <span>{selectedAuthor}</span> <ChevronRight className="w-2.5 h-2.5" />
            <span className="text-primary">{selectedBook}</span>
            {selectedChapter && (
              <>
                <ChevronRight className="w-2.5 h-2.5" />
                <span className="text-primary/70">{selectedChapter}</span>
              </>
            )}
          </nav>
          <h1 className="text-5xl font-headline text-on-background font-bold tracking-tight max-w-7xl leading-tight">
            {selectedChapter || 'Chapter Segment'}
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
              disabled={historyIndex === historyLength - 1}
              className="p-2 hover:bg-surface-container-high transition-colors rounded-sm disabled:opacity-30 disabled:cursor-not-allowed" 
              title="Redo"
            >
              <Redo2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Bento Layout Content */}
      <div className="grid grid-cols-12 gap-8">
        {/* Left Column: Stats & Metadata */}
        <div className="col-span-12 lg:col-span-4 space-y-8">
          <section className="bg-surface-container-low p-8 rounded-sm editorial-shadow">
            <h3 className="text-xs font-bold uppercase tracking-widest text-secondary mb-4">Current Book</h3>
            <h2 className="text-2xl font-headline font-bold text-on-background leading-tight">
              {selectedBook}
            </h2>
          </section>

          <section className="bg-surface-container-low p-8 rounded-sm editorial-shadow">
            <h3 className="text-xs font-bold uppercase tracking-widest text-secondary mb-6">Segment Metrics</h3>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Segmentation Logic</span>
              <span className="text-[10px] font-label bg-primary/10 text-primary px-2 py-0.5 rounded-full uppercase font-bold">Active</span>
            </div>
            <div className="w-full bg-surface-container-high h-1 mb-8 overflow-hidden">
              <div className="bg-primary h-full w-full"></div>
            </div>
            <div className="space-y-4 mb-8">
              <div className="flex justify-between items-center text-sm">
                <span className="text-secondary">Total Segments</span>
                <span className="font-semibold">{segments.length} blocks</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-secondary">Total Word Count</span>
                <span className="font-semibold">
                  {segments.reduce((acc, s) => acc + s.content.split(' ').length, 0).toLocaleString()} words
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

        {/* Right Column: Segmented Content Display */}
        <div className="col-span-12 lg:col-span-8 max-h-[calc(100vh-18rem)] overflow-y-auto pl-6 pr-4 custom-scrollbar">
          <section className="space-y-6">
            <AnimatePresence mode="popLayout">
              {segments.map((segment) => (
                <motion.div
                  key={segment.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  viewport={{ once: true }}
                  className="group relative bg-surface-container-low p-8 rounded-sm border border-transparent hover:border-outline-variant/30 transition-all editorial-shadow z-10"
                >
                  <div className="absolute -left-3 top-8 w-6 h-6 bg-surface-container-highest border border-outline-variant/20 rounded-full flex items-center justify-center text-[10px] font-bold text-secondary z-20 shadow-sm">
                    {segment.id}
                  </div>
                  <p className="font-headline text-lg leading-relaxed text-on-background/80 italic">
                    {segment.content}
                  </p>
                  <div className="mt-6 pt-4 border-t border-outline-variant/10 flex justify-end items-center">
                    <button 
                      onClick={() => onDeleteSegment(segment.id)}
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
                <p>No segments remaining.</p>
                <button 
                  onClick={onRefresh}
                  className="mt-4 text-primary font-bold hover:underline"
                >
                  Restore all segments
                </button>
              </div>
            )}
          </section>
        </div>
      </div>

    </div>
  );
}
