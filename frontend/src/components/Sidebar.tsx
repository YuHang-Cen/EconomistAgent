import { FileUp } from 'lucide-react';
import { Author } from '../types';

interface SidebarProps {
  authors: Author[];
}

export default function Sidebar({ authors }: SidebarProps) {
  return (
    <section className="col-span-12 lg:col-span-4 space-y-8">
      <div className="bg-surface-container-low p-8 rounded-sm editorial-shadow sticky top-32">
        <h2 className="font-headline text-2xl mb-6 italic">Quick Import</h2>
        <div className="border-2 border-dashed border-outline-variant/30 rounded-sm p-12 text-center group hover:border-primary/50 transition-colors cursor-pointer bg-white/50">
          <FileUp className="w-10 h-10 text-outline-variant mx-auto mb-4 group-hover:scale-110 transition-transform" />
          <p className="font-body text-sm text-secondary mb-2">Drag & drop PDF manuscripts here</p>
          <p className="font-label text-[10px] text-outline-variant uppercase tracking-widest">or click to browse local archive</p>
        </div>
        <div className="mt-8 space-y-4">
          <label className="block">
            <span className="font-label text-[10px] uppercase tracking-widest text-secondary block mb-2">Select Author</span>
            <select className="w-full bg-white border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all">
              {authors.map(author => (
                <option key={author.id}>{author.name}</option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </section>
  );
}
