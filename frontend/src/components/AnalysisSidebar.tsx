import { Plus, ChevronDown, Trash2, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'motion/react';
import { AUTHORS, HISTORY_DATA } from '../data/mockData';

interface AnalysisSidebarProps {
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewAnalysis: () => void;
}

export default function AnalysisSidebar({ selectedId, onSelect, onNewAnalysis }: AnalysisSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedAuthors, setExpandedAuthors] = useState<string[]>(['Adam Smith']);

  const toggleAuthor = (name: string) => {
    if (isCollapsed) return;
    setExpandedAuthors(prev => 
      prev.includes(name) ? prev.filter(a => a !== name) : [...prev, name]
    );
  };

  return (
    <motion.aside 
      initial={false}
      animate={{ width: isCollapsed ? 64 : 320 }}
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

      <div className={`flex-1 flex flex-col overflow-y-auto custom-scrollbar`}>
        {/* New Analysis Button */}
        <div className={`p-6 ${isCollapsed ? 'pt-16 px-2' : ''}`}>
          <button 
            onClick={onNewAnalysis}
            className={`w-full flex items-center justify-center gap-3 transition-colors py-4 px-6 rounded-sm border border-outline-variant/20 shadow-sm ${
              selectedId === null ? 'bg-primary text-on-primary' : 'bg-surface-container-highest hover:bg-surface-dim text-on-surface'
            } ${isCollapsed ? 'px-0 w-10 h-10 mx-auto' : ''}`}
            title="New Analysis"
          >
            <Plus className={`w-4 h-4 shrink-0 ${selectedId === null ? 'text-on-primary' : 'text-primary'}`} />
            {!isCollapsed && <span className="font-label text-xs font-bold uppercase tracking-widest">New Analysis</span>}
          </button>
        </div>

        {/* History Groups */}
        <div className={`flex-grow px-4 pb-8 ${isCollapsed ? 'px-2' : ''}`}>
          <div className="space-y-4">
            {HISTORY_DATA.map((group) => {
              const author = AUTHORS.find(a => a.id === group.authorId);
              if (!author) return null;

              return (
                <div key={author.id} className="group">
                  <div 
                    onClick={() => toggleAuthor(author.name)}
                    className={`flex items-center justify-between cursor-pointer py-2 px-2 hover:bg-surface-container transition-colors rounded-sm ${isCollapsed ? 'justify-center' : ''}`}
                  >
                    <div className="flex items-center gap-3">
                      {!isCollapsed && (
                        <ChevronDown 
                          className={`w-4 h-4 text-secondary transition-transform duration-200 ${
                            expandedAuthors.includes(author.name) ? 'rotate-0' : '-rotate-90'
                          }`} 
                        />
                      )}
                      <div className={`w-4 h-4 rounded-full bg-primary/10 flex items-center justify-center text-[8px] font-bold text-primary shrink-0`}>
                        {author.name.charAt(0)}
                      </div>
                      {!isCollapsed && (
                        <span className="font-label text-[10px] font-bold uppercase tracking-[0.15em] text-on-surface-variant truncate">
                          {author.name}
                        </span>
                      )}
                    </div>
                    {!isCollapsed && (
                      <span className="font-label text-[9px] text-outline-variant px-1.5 py-0.5 border border-outline-variant/20 rounded">
                        {group.items.length}
                      </span>
                    )}
                  </div>
                  
                  {!isCollapsed && expandedAuthors.includes(author.name) && (
                    <div className="space-y-1 pl-6 mt-2">
                      {group.items.map((item) => (
                        <div 
                          key={item.id}
                          onClick={() => onSelect(item.id)}
                          className={`group/item flex items-center justify-between p-2 rounded-sm cursor-pointer transition-all ${
                            selectedId === item.id 
                              ? 'border-l-2 border-primary bg-primary/5 text-primary font-medium' 
                              : 'hover:bg-surface-container-highest text-secondary'
                          }`}
                        >
                          <span className="font-body text-sm truncate pr-4">{item.title}</span>
                          <button className="opacity-0 group-hover/item:opacity-100 transition-opacity p-1 text-outline-variant hover:text-error">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
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
