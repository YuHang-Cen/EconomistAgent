import { ChevronDown, ChevronRight, User, BookOpen, Book, Trash2, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'motion/react';
import { AUTHORS } from '../data/mockData';

interface SegmentSidebarProps {
  authors: typeof AUTHORS;
  selectedAuthor: string;
  selectedBook: string;
  selectedChapter: string;
  onSelect: (author: string, book: string, chapter: string) => void;
  onDeleteChapter: (authorId: string, bookId: string, chapterId: string) => void;
}

export default function SegmentSidebar({ 
  authors,
  selectedAuthor, 
  selectedBook, 
  selectedChapter, 
  onSelect,
  onDeleteChapter
}: SegmentSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedAuthors, setExpandedAuthors] = useState<string[]>(['Adam Smith']);
  const [expandedBooks, setExpandedBooks] = useState<string[]>(['The Wealth of Nations']);

  const toggleAuthor = (author: string) => {
    if (isCollapsed) return;
    setExpandedAuthors(prev => 
      prev.includes(author) ? prev.filter(a => a !== author) : [...prev, author]
    );
  };

  const toggleBook = (book: string) => {
    if (isCollapsed) return;
    setExpandedBooks(prev => 
      prev.includes(book) ? prev.filter(b => b !== book) : [...prev, book]
    );
  };

  return (
    <motion.aside 
      initial={false}
      animate={{ width: isCollapsed ? 64 : 288 }}
      className="bg-surface-container-low border-r border-outline-variant/10 flex flex-col shrink-0 overflow-hidden relative group"
    >
      {/* Collapse Toggle Button */}
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        className={`absolute right-4 top-4 z-20 p-2 hover:bg-surface-container-high rounded-sm text-secondary hover:text-primary transition-all duration-300 ${
          isCollapsed ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        }`}
        title={isCollapsed ? "展开导航栏" : "折叠导航栏"}
      >
        {isCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
      </button>

      <div className={`flex-1 flex flex-col ${isCollapsed ? 'items-center' : ''} overflow-y-auto custom-scrollbar`}>
        <nav className={`flex-1 px-4 space-y-1 ${isCollapsed ? 'pt-16' : 'pt-8'}`}>
          <div className="space-y-1">
            {authors.map((author) => (
              <div key={author.id}>
                <div 
                  onClick={() => toggleAuthor(author.name)}
                  className={`rounded-sm flex items-center gap-3 px-6 py-3 cursor-pointer transition-colors ${
                    selectedAuthor === author.name ? 'text-on-background font-bold bg-white/50' : 'text-secondary hover:bg-white/30'
                  } ${isCollapsed ? 'justify-center px-0' : ''}`}
                >
                  {!isCollapsed && (expandedAuthors.includes(author.name) ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />)}
                  <User className={`w-4 h-4 ${selectedAuthor === author.name ? 'text-primary' : 'text-primary/70'}`} />
                  {!isCollapsed && <span className="text-sm">{author.name}</span>}
                </div>
                
                {!isCollapsed && expandedAuthors.includes(author.name) && (
                  <div className="ml-6 space-y-1">
                    {author.books.map((book) => (
                      <div key={book.id}>
                        <div 
                          onClick={() => toggleBook(book.title)}
                          className={`flex items-center gap-3 px-6 py-2.5 cursor-pointer transition-all ${
                            selectedBook === book.title ? 'text-primary font-medium' : 'text-secondary hover:translate-x-1'
                          }`}
                        >
                          {expandedBooks.includes(book.title) ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          <BookOpen className={`w-4 h-4 ${selectedBook === book.title ? 'text-primary' : 'text-primary/70'}`} />
                          <span className="text-sm">{book.title}</span>
                        </div>
                        
                        {expandedBooks.includes(book.title) && (
                          <div className="ml-10 space-y-1 border-l border-outline-variant/20">
                            {book.chapters.map((chapter) => (
                              <div 
                                key={chapter.id}
                                onClick={() => onSelect(author.name, book.title, chapter.title)}
                                className={`group flex items-center justify-between px-6 py-2 cursor-pointer text-xs transition-all ${
                                  selectedChapter === chapter.title 
                                    ? 'text-primary font-semibold bg-primary/10 rounded-sm' 
                                    : 'text-secondary hover:text-primary hover:translate-x-1'
                                }`}
                              >
                                <div className="flex items-center gap-3 truncate">
                                  <Book className="w-3 h-3 shrink-0" />
                                  <span className="truncate">{chapter.title}</span>
                                </div>
                                <button 
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteChapter(author.id, book.id, chapter.id);
                                  }}
                                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-outline-variant hover:text-error shrink-0"
                                  title="Delete Chapter"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </nav>
      </div>
    </motion.aside>
  );
}
