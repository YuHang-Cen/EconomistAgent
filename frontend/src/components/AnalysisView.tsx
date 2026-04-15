import { ChevronDown, CheckCircle2, Sparkles, ChevronRight } from 'lucide-react';
import { motion } from 'motion/react';
import { ARTICLES } from '../data/articles';
import { Author } from '../types';

interface AnalysisViewProps {
  authors: Author[];
  selectedId: string | null;
  onGenerate: () => void;
}

export default function AnalysisView({ authors, selectedId, onGenerate }: AnalysisViewProps) {
  const article = selectedId ? ARTICLES[selectedId] : null;

  if (article) {
    return (
      <main className="flex-grow bg-surface overflow-y-auto custom-scrollbar">
        <div className="px-12 py-12">
          {/* Breadcrumb */}
          <nav className="mb-12">
            <ol className="flex items-center gap-2 font-label text-[10px] tracking-[0.2em] text-secondary font-semibold uppercase">
              <li>Analysis</li>
              <li className="text-outline-variant opacity-50">›</li>
              <li className="text-primary">{article.author}</li>
            </ol>
          </nav>

          {/* Article Header */}
          <header className="mb-16">
            <h1 className="font-headline text-6xl font-bold text-on-surface mb-12 tracking-tight leading-[1.1]">
              {article.title}
            </h1>
            
            <div className="grid grid-cols-3 gap-12 pt-8 border-t border-outline-variant/10">
              <div>
                <span className="block font-label text-[10px] uppercase tracking-widest text-outline-variant mb-2">Author</span>
                <span className="font-body text-sm font-semibold text-on-surface">{article.author}</span>
              </div>
              <div>
                <span className="block font-label text-[10px] uppercase tracking-widest text-outline-variant mb-2">Topic</span>
                <span className="font-body text-sm font-semibold text-on-surface">{article.topic}</span>
              </div>
              <div>
                <span className="block font-label text-[10px] uppercase tracking-widest text-outline-variant mb-2">Generation Date</span>
                <span className="font-body text-sm font-semibold text-on-surface">{article.date}</span>
              </div>
            </div>
          </header>

          {/* Article Content */}
          <article className="prose prose-slate max-w-none">
            {article.content.map((block, idx) => {
              if (block.type === 'heading') {
                return (
                  <h2 key={idx} className="font-headline text-3xl font-bold text-primary mt-12 mb-8">
                    {block.text}
                  </h2>
                );
              }
              return (
                <p key={idx} className="font-body text-lg text-secondary leading-relaxed mb-8 first-letter:text-7xl first-letter:font-headline first-letter:float-left first-letter:mr-3 first-letter:mt-2 first-letter:text-primary">
                  {block.text}
                </p>
              );
            })}
          </article>

          {/* Methodological Footprint */}
          {(article.mainSkill || article.subSkills) && (
            <section className="mt-20 pt-12 border-t-2 border-primary/10">
              <div className="flex items-center gap-3 mb-8">
                <Sparkles className="w-5 h-5 text-primary" />
                <h3 className="font-label text-xs font-bold uppercase tracking-[0.2em] text-primary">
                  Methodological Footprint
                </h3>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {article.mainSkill && (
                  <div className="md:col-span-1">
                    <span className="block font-label text-[10px] uppercase tracking-widest text-outline-variant mb-3">Main Skill</span>
                    <div className="bg-primary/5 border border-primary/10 p-4 rounded-sm">
                      <span className="font-headline text-lg font-bold text-primary block mb-1">{article.mainSkill}</span>
                      <span className="text-[10px] font-label text-primary/60 uppercase font-bold tracking-tighter">Main Skill Applied</span>
                    </div>
                  </div>
                )}
                
                {article.subSkills && article.subSkills.length > 0 && (
                  <div className="md:col-span-2">
                    <span className="block font-label text-[10px] uppercase tracking-widest text-outline-variant mb-3">Sub Skills</span>
                    <div className="flex flex-wrap gap-3">
                      {article.subSkills.map((skill, index) => (
                        <div key={index} className="bg-surface-container-high/50 border border-outline-variant/20 px-4 py-3 rounded-sm flex items-center gap-3">
                          <div className="w-1.5 h-1.5 rounded-full bg-primary/40" />
                          <span className="font-body text-sm font-medium text-secondary">{skill}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
              <p className="mt-10 text-[10px] font-body text-outline-variant italic leading-relaxed max-w-2xl">
                Note: This synthesis was constructed by mapping the research topic against the identified theoretical patterns and execution skeletons derived from the author's primary textual archive.
              </p>
            </section>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="flex-grow bg-surface overflow-y-auto custom-scrollbar">
      <div className="px-12 py-12">
        {/* Breadcrumb */}
        <nav className="mb-12">
          <ol className="flex items-center gap-2 font-label text-[10px] tracking-[0.2em] text-secondary font-semibold uppercase">
            <li>Analysis</li>
            <li className="text-outline-variant opacity-50">›</li>
            <li className="text-primary">New Analysis</li>
          </ol>
        </nav>

        {/* Hero Header */}
        <header className="mb-16">
          <h1 className="font-headline text-5xl font-light text-on-surface mb-6 tracking-tight leading-tight">
            Synthesize an economic <span className="italic">perspective</span> through academic rigor.
          </h1>
          <p className="font-body text-lg text-secondary max-w-2xl leading-relaxed">
            Consult the digital archives and prompt the system to generate a comprehensive synthesis based on historical economic schools of thought.
          </p>
        </header>

        {/* Input Section */}
        <div className="bg-surface-container-low p-10 rounded-sm editorial-shadow">
          <div className="space-y-12">
            {/* Economist Selector */}
            <div className="space-y-4">
              <label className="block font-label text-xs font-bold text-on-surface-variant uppercase tracking-widest">
                Select Academic Persona
              </label>
              <div className="relative group">
                <select className="w-full appearance-none bg-surface-container-lowest border-b border-outline-variant/20 focus:border-primary px-4 py-4 pr-10 outline-none font-headline text-2xl transition-all cursor-pointer">
                  {authors.map((author) => (
                    <option key={author.id}>{author.name}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-secondary pointer-events-none group-focus-within:rotate-180 transition-transform w-6 h-6" />
              </div>
              <p className="font-body text-sm text-secondary italic">
                Your inquiry will be processed through the specific theoretical framework of the chosen economist.
              </p>
            </div>

            {/* Research Topic Input */}
            <div className="space-y-4">
              <label className="block font-label text-xs font-bold text-on-surface-variant uppercase tracking-widest">
                Define the Research Topic
              </label>
              <div className="bg-surface-container-lowest p-8 border-b-2 border-outline-variant/15 focus-within:border-primary transition-colors">
                <textarea 
                  className="w-full bg-transparent border-none focus:ring-0 font-headline text-3xl leading-snug placeholder:text-outline-variant/40 resize-none outline-none" 
                  placeholder="e.g., The implications of digital currency on central bank sovereignty in the 21st century..." 
                  rows={4}
                />
              </div>
            </div>

            {/* Action Area */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pt-4">
              <div className="flex flex-col sm:flex-row sm:items-center gap-6">
                <div className="flex items-center text-xs font-label text-secondary gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary fill-primary/20" />
                  <span>Archive Access Verified</span>
                </div>
                <div className="flex items-center text-xs font-label text-secondary gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary fill-primary/20" />
                  <span>Model: Journal-Standard-v4</span>
                </div>
              </div>
              <button 
                onClick={onGenerate}
                className="flex items-center justify-center gap-4 bg-primary text-on-primary px-10 py-5 rounded-sm hover:bg-primary-dim transition-all shadow-xl shadow-primary/10 group"
              >
                <span className="font-label text-sm font-bold uppercase tracking-widest">Generate Article</span>
                <Sparkles className="w-5 h-5 group-hover:rotate-12 transition-transform" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
