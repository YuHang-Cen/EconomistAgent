import { motion } from 'motion/react';
import { Sparkles } from 'lucide-react';

interface LandingPageProps {
  onStart: () => void;
}

export default function LandingPage({ onStart }: LandingPageProps) {
  return (
    <div className="fixed inset-0 z-[100] bg-background flex flex-col items-center justify-center overflow-hidden">
      {/* Background Decorative Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px]" />
      </div>

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="relative z-10 flex flex-col items-center text-center px-6"
      >
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="mb-8 p-3 bg-primary/10 rounded-full"
        >
          <Sparkles className="w-8 h-8 text-primary" />
        </motion.div>

        <h1 className="font-headline text-7xl md:text-8xl font-bold tracking-tighter text-on-background mb-6 leading-tight">
          The Economist <span className="italic font-light">Agent</span>
        </h1>
        
        <p className="font-body text-xl md:text-2xl text-secondary max-w-2xl mb-12 leading-relaxed font-light">
          An advanced digital archive and analytical engine for the classical economic lexicon. 
          Synthesizing historical perspectives through modern computational rigor.
        </p>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onStart}
          className="group relative px-12 py-5 bg-on-background text-background rounded-sm font-label text-sm font-bold uppercase tracking-[0.3em] overflow-hidden transition-all shadow-2xl shadow-on-background/20"
        >
          <span className="relative z-10">Start Exploration</span>
          <div className="absolute inset-0 bg-primary translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
        </motion.button>

        <div className="mt-24 flex items-center gap-8 opacity-30">
          <div className="h-px w-12 bg-outline-variant" />
          <span className="font-label text-[10px] uppercase tracking-[0.4em]">Est. 2024 • Academic Modern Collective</span>
          <div className="h-px w-12 bg-outline-variant" />
        </div>
      </motion.div>

      {/* Subtle Texture Overlay */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[url('https://www.transparenttextures.com/patterns/paper-fibers.png')]" />
    </div>
  );
}
