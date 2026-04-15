/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import AuthorSection from './components/AuthorSection';
import CreateAuthorModal from './components/CreateAuthorModal';
import SegmentSidebar from './components/SegmentSidebar';
import SegmentView from './components/SegmentView';
import MethodologySidebar from './components/MethodologySidebar';
import MethodologyView from './components/MethodologyView';
import AnalysisSidebar from './components/AnalysisSidebar';
import AnalysisView from './components/AnalysisView';
import LandingPage from './components/LandingPage';
import SettingsModal from './components/SettingsModal';
import { AUTHORS } from './data/mockData';
import { motion, AnimatePresence } from 'motion/react';
import { useCallback } from 'react';

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

interface SegmentState {
  authors: typeof AUTHORS;
  segments: typeof INITIAL_SEGMENTS;
}

type Tab = 'archive' | 'analysis' | 'methodology' | 'answer' | 'landing';

export default function App() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('landing');

  // Segment state with history (Primary source for authors and segments)
  const [segmentState, setSegmentState] = useState<SegmentState>({
    authors: AUTHORS,
    segments: INITIAL_SEGMENTS
  });
  const [segmentHistory, setSegmentHistory] = useState<SegmentState[]>([{
    authors: AUTHORS,
    segments: INITIAL_SEGMENTS
  }]);
  const [segmentHistoryIndex, setSegmentHistoryIndex] = useState(0);
  
  // Analysis selection state
  const [analysisSelection, setAnalysisSelection] = useState({
    author: 'Adam Smith',
    book: 'The Wealth of Nations',
    chapter: 'Chapter 2: The Principle of Exchange'
  });

  const [methodologySelection, setMethodologySelection] = useState('Adam Smith');
  
  // Answer selection state
  const [answerSelection, setAnswerSelection] = useState<string | null>(null);

  const handleAnalysisSelect = (author: string, book: string, chapter: string) => {
    setAnalysisSelection({ author, book, chapter });
  };

  const handleMethodologySelect = (economist: string) => {
    setMethodologySelection(economist);
  };

  const handleAnswerSelect = (id: string) => {
    setAnswerSelection(id);
  };

  const handleNewAnalysis = () => {
    setAnswerSelection(null);
  };

  const handleGenerate = () => {
    // Simulate generation by selecting the mock article
    setAnswerSelection('as-3');
  };

  const updateSegmentState = useCallback((newState: SegmentState) => {
    const newHistory = segmentHistory.slice(0, segmentHistoryIndex + 1);
    newHistory.push(newState);
    setSegmentHistory(newHistory);
    setSegmentHistoryIndex(newHistory.length - 1);
    setSegmentState(newState);
  }, [segmentHistory, segmentHistoryIndex]);

  const handleUndoSegment = () => {
    if (segmentHistoryIndex > 0) {
      const prevIndex = segmentHistoryIndex - 1;
      setSegmentHistoryIndex(prevIndex);
      setSegmentState(segmentHistory[prevIndex]);
    }
  };

  const handleRedoSegment = () => {
    if (segmentHistoryIndex < segmentHistory.length - 1) {
      const nextIndex = segmentHistoryIndex + 1;
      setSegmentHistoryIndex(nextIndex);
      setSegmentState(segmentHistory[nextIndex]);
    }
  };

  const handleDeleteChapter = (authorId: string, bookId: string, chapterId: string) => {
    const newAuthors = segmentState.authors.map(author => {
      if (author.id === authorId) {
        return {
          ...author,
          books: author.books.map(book => {
            if (book.id === bookId) {
              return {
                ...book,
                chapters: book.chapters.filter(c => c.id !== chapterId)
              };
            }
            return book;
          })
        };
      }
      return author;
    });
    updateSegmentState({ ...segmentState, authors: newAuthors });
  };

  const handleDeleteSegment = (id: string) => {
    const newSegments = segmentState.segments.filter(s => s.id !== id);
    updateSegmentState({ ...segmentState, segments: newSegments });
  };

  const handleRefreshSegments = () => {
    updateSegmentState({ ...segmentState, segments: INITIAL_SEGMENTS });
  };

  const handleRemoveManuscript = (authorId: string, manuscriptId: string) => {
    const newAuthors = segmentState.authors.map(author => {
      if (author.id === authorId) {
        const manuscript = author.manuscripts.find(m => m.id === manuscriptId);
        // Try to match book title with manuscript title (ignoring year in parentheses)
        const manuscriptTitle = manuscript?.title.split(' (')[0];

        return {
          ...author,
          manuscripts: author.manuscripts.filter(m => m.id !== manuscriptId),
          manuscriptsCount: author.manuscriptsCount - 1,
          books: author.books.filter(book => book.title !== manuscriptTitle)
        };
      }
      return author;
    });
    updateSegmentState({ ...segmentState, authors: newAuthors });
  };

  return (
    <div className="min-h-screen bg-background text-on-background font-body flex flex-col">
      <Navbar 
        activeTab={activeTab} 
        onTabChange={setActiveTab} 
        onSettingsOpen={() => setIsSettingsOpen(true)}
      />
      
      <AnimatePresence mode="wait">
        {activeTab === 'landing' && (
          <LandingPage onStart={() => setActiveTab('archive')} />
        )}
      </AnimatePresence>

      <main className="pt-20 flex-grow flex flex-col">
        {activeTab === 'archive' ? (
          <div className="max-w-7xl mx-auto px-12 py-12 w-full">
            {/* Header Section */}
            <header className="flex flex-col md:flex-row justify-between items-start md:items-end mb-16 gap-6">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5 }}
              >
                <h1 className="font-headline text-5xl font-medium tracking-tight text-on-background mb-4">
                  Textual Archive
                </h1>
                <p className="font-body text-secondary text-lg max-w-xl leading-relaxed">
                  Manage the foundational manuscripts of the economic lexicon. Import new source material and organize research by author and school of thought.
                </p>
              </motion.div>
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setIsModalOpen(true)}
                className="bg-primary text-on-primary px-8 py-3 rounded-sm font-label text-sm font-semibold tracking-wide hover:bg-primary-dim transition-all shadow-md active:translate-y-px"
              >
                Create New Author
              </motion.button>
            </header>

            <div className="grid grid-cols-12 gap-8">
              {/* Sidebar */}
              <Sidebar authors={segmentState.authors} />

              {/* Main Content */}
              <section className="col-span-12 lg:col-span-8 space-y-12">
                {segmentState.authors.map((author) => (
                  <AuthorSection 
                    key={author.id} 
                    author={author} 
                    onRemoveManuscript={(manuscriptId) => handleRemoveManuscript(author.id, manuscriptId)}
                  />
                ))}
              </section>
            </div>
          </div>
        ) : activeTab === 'analysis' ? (
          <div className="flex flex-1 overflow-hidden">
            <SegmentSidebar 
              authors={segmentState.authors}
              selectedAuthor={analysisSelection.author}
              selectedBook={analysisSelection.book}
              selectedChapter={analysisSelection.chapter}
              onSelect={handleAnalysisSelect}
              onDeleteChapter={handleDeleteChapter}
            />
            <SegmentView 
              selectedAuthor={analysisSelection.author}
              selectedBook={analysisSelection.book}
              selectedChapter={analysisSelection.chapter}
              segments={segmentState.segments}
              onDeleteSegment={handleDeleteSegment}
              onUndo={handleUndoSegment}
              onRedo={handleRedoSegment}
              onRefresh={handleRefreshSegments}
              historyIndex={segmentHistoryIndex}
              historyLength={segmentHistory.length}
            />
          </div>
        ) : activeTab === 'methodology' ? (
          <div className="flex flex-1 overflow-hidden">
            <MethodologySidebar 
              authors={segmentState.authors}
              selectedEconomist={methodologySelection}
              onSelect={handleMethodologySelect}
            />
            <MethodologyView 
              selectedEconomist={methodologySelection}
            />
          </div>
        ) : activeTab === 'answer' ? (
          <div className="flex flex-1 overflow-hidden">
            <AnalysisSidebar 
              selectedId={answerSelection}
              onSelect={handleAnswerSelect}
              onNewAnalysis={handleNewAnalysis}
            />
            <AnalysisView 
              authors={segmentState.authors}
              selectedId={answerSelection}
              onGenerate={handleGenerate}
            />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-secondary italic">
            View coming soon...
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="py-12 px-12 border-t border-outline-variant/10 bg-surface-container-low/30 mt-auto">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-[10px] font-label uppercase tracking-[0.2em] text-outline-variant">
          <span>The Lexicon Project • Archive Node Alpha</span>
          <span>Est. 2024 • Academic Modern Collective</span>
        </div>
      </footer>

      {/* Modals */}
      <AnimatePresence>
        {isModalOpen && (
          <CreateAuthorModal 
            isOpen={isModalOpen} 
            onClose={() => setIsModalOpen(false)} 
          />
        )}
        {isSettingsOpen && (
          <SettingsModal 
            isOpen={isSettingsOpen} 
            onClose={() => setIsSettingsOpen(false)} 
          />
        )}
      </AnimatePresence>
    </div>
  );
}

