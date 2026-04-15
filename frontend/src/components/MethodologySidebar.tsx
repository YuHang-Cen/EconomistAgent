import { UserSearch, ChevronRight, ChevronDown, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'motion/react';
import { Author } from '../types';

interface MethodologySidebarProps {
  authors: Author[];
  selectedEconomist: string;
  onSelect: (economist: string) => void;
}

export default function MethodologySidebar({ authors, selectedEconomist, onSelect }: MethodologySidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

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

      <div className={`flex-grow space-y-1 overflow-y-auto custom-scrollbar ${isCollapsed ? 'pt-16' : 'py-6 pl-4 pr-2'}`}>
        {/* Economists Section */}
        <div className="mb-2">
          <div 
            onClick={() => !isCollapsed && setIsExpanded(!isExpanded)}
            className={`flex items-center gap-3 px-4 py-3 text-primary font-bold bg-surface-container-high/50 rounded-r-lg cursor-pointer ${isCollapsed ? 'justify-center px-0 rounded-none' : ''}`}
          >
            {!isCollapsed && (isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />)}
            <UserSearch className="w-4 h-4" />
            {!isCollapsed && <span className="font-label text-sm">Economists</span>}
          </div>
          
          {!isCollapsed && isExpanded && (
            <div className="ml-12 mt-1 space-y-1">
              {authors.map((author) => (
                <button
                  key={author.id}
                  onClick={() => onSelect(author.name)}
                  className={`block w-full text-left py-2 text-sm font-label border-l-2 pl-4 transition-all ${
                    selectedEconomist === author.name
                      ? 'text-primary border-primary font-bold'
                      : 'text-secondary border-transparent hover:text-primary hover:border-primary/50'
                  }`}
                >
                  {author.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.aside>
  );
}
