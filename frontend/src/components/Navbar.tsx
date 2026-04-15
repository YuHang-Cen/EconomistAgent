import { Search, UserCircle, Settings } from 'lucide-react';

interface NavbarProps {
  activeTab: 'archive' | 'analysis' | 'methodology' | 'answer' | 'landing';
  onTabChange: (tab: 'archive' | 'analysis' | 'methodology' | 'answer' | 'landing') => void;
  onSettingsOpen: () => void;
}

export default function Navbar({ activeTab, onTabChange, onSettingsOpen }: NavbarProps) {
  const showSearch = activeTab === 'archive';

  const navItems = [
    { id: 'archive', label: 'Archive' },
    { id: 'analysis', label: 'Segment' },
    { id: 'methodology', label: 'Methodology' },
    { id: 'answer', label: 'Analysis' },
  ] as const;

  return (
    <nav className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-xl shadow-sm border-b border-outline-variant/10">
      <div className="flex justify-between items-center px-8 h-20 max-w-screen-2xl mx-auto">
        <div className="flex items-center gap-12">
          <span 
            onClick={() => onTabChange('landing')}
            className="text-2xl cursor-pointer active:opacity-70 transition-opacity font-headline font-bold tracking-tight text-blue-900"
          >
            The Economist Agent
          </span>
          <div className="hidden md:flex items-center gap-8 font-headline font-medium tracking-tight">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`transition-all cursor-pointer active:opacity-70 pb-1 ${
                  activeTab === item.id
                    ? 'text-on-background font-bold border-b-2 border-on-background'
                    : 'text-secondary hover:text-on-background'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-6">
          {showSearch && (
            <div className="relative group">
              <input
                className="bg-surface-container-low border-none rounded-sm px-4 py-2 w-64 focus:ring-1 focus:ring-primary outline-none font-label text-sm transition-all duration-300 group-hover:bg-surface-container-high"
                placeholder="Search archive..."
                type="text"
              />
              <Search className="absolute right-3 top-2.5 w-4 h-4 text-outline-variant" />
            </div>
          )}
          <UserCircle className="w-6 h-6 text-on-background cursor-pointer active:opacity-70" />
          <Settings 
            onClick={onSettingsOpen}
            className="w-6 h-6 text-on-background cursor-pointer active:opacity-70 hover:text-primary transition-colors" 
          />
        </div>
      </div>
    </nav>
  );
}
