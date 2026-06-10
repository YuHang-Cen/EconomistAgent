import { CheckCircle2, ChevronDown, ChevronRight, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import type { AnswerVM, Author, Job } from "../types";

interface AnalysisViewProps {
  authors: Author[];
  selectedAuthorId: string | null;
  query: string;
  creating: boolean;
  selectedAnswer: AnswerVM | null;
  selectedJob: Job | null;
  runningJob: Job | null;
  onSelectAuthor: (authorId: string) => void;
  onQueryChange: (value: string) => void;
  onGenerate: () => Promise<void> | void;
}

function formatGenerateDate(value: string | null | undefined): string {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleString();
}

function formatJobStatus(value: string | null | undefined): string {
  const text = (value || "queued").trim().toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatJobStage(value: string | null | undefined): string {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    extract: "Extract",
    segment_sync: "Segment Sync",
    analyze: "Analyze",
    main_skill: "Main Skill",
    sub_skill: "Sub Skill",
    render: "Render",
    select_skills: "Select Skills",
    answer: "Answer",
  };
  return labels[normalized] || "Pending";
}

function normalizeProgress(value: number | null | undefined): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function renderEssayMarkdown(
  markdown: string,
  options?: { muted?: boolean; headingLevel?: "h2" | "h3" }
) {
  const headingLevel = options?.headingLevel ?? "h2";
  const paragraphClass = options?.muted
    ? "font-body text-[1.05rem] text-secondary/90 leading-[1.85] mb-6"
    : "font-body text-[1.1rem] text-secondary leading-[1.8] mb-6";
  const headingClass =
    headingLevel === "h3"
      ? "font-headline text-2xl font-bold text-on-surface mt-12 mb-5 leading-snug"
      : "font-headline text-3xl font-bold text-on-surface mt-14 mb-6 leading-snug";

  return markdown.split(/\n+/).map((block, i) => {
    const text = block.trim();
    if (!text) return null;

    if (text.startsWith("#")) {
      const headingText = text.replace(/^#+\s*/, "");
      if (headingLevel === "h3") {
        return (
          <h3 key={i} className={headingClass}>
            {headingText}
          </h3>
        );
      }
      return (
        <h2 key={i} className={headingClass}>
          {headingText}
        </h2>
      );
    }

    return (
      <p key={i} className={paragraphClass}>
        {text}
      </p>
    );
  });
}

export default function AnalysisView({
  authors,
  selectedAuthorId,
  query,
  creating,
  selectedAnswer,
  selectedJob,
  runningJob,
  onSelectAuthor,
  onQueryChange,
  onGenerate,
}: AnalysisViewProps) {
  const showRunningProgress =
    !!runningJob && (runningJob.status === "queued" || runningJob.status === "running");
  const runningProgress = normalizeProgress(runningJob?.progress);

  if (selectedAnswer) {
    const generateDateValue = formatGenerateDate(
      selectedAnswer.generatedAt ?? selectedJob?.finishedAt ?? null
    );
    const authorDisplayName =
      authors.find((a) => a.authorId === selectedAuthorId)?.authorName || "Unknown Author";

    return (
      <main className="flex-grow bg-surface overflow-y-auto custom-scrollbar">
        <div className="px-12 py-12 max-w-6xl mx-auto">
          <nav className="mb-12">
            <ol className="flex items-center gap-2 font-label text-[10px] tracking-[0.2em] text-secondary font-semibold uppercase">
              <li>Analysis</li>
              <li>
                <ChevronRight className="w-3 h-3 text-outline-variant opacity-50" />
              </li>
              <li>{authorDisplayName}</li>
              <li>
                <ChevronRight className="w-3 h-3 text-outline-variant opacity-50" />
              </li>
              <li className="text-primary">{selectedAnswer.answer.topic || "Answer"}</li>
            </ol>
          </nav>

          <header className="mb-12">
            <h1 className="font-headline text-5xl lg:text-[3.5rem] font-bold text-on-surface mb-12 tracking-tight leading-[1.15]">
              {selectedAnswer.answer.title || "Generated Answer"}
            </h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pb-6 border-b border-outline-variant/10">
              <div>
                <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                  Author
                </span>
                <span className="font-body text-sm font-semibold text-on-surface">
                  {authorDisplayName}
                </span>
              </div>
              <div>
                <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                  Topic
                </span>
                <span className="font-body text-sm font-semibold text-on-surface">
                  {selectedAnswer.answer.topic}
                </span>
              </div>
              <div>
                <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                  Generate Date
                </span>
                <span className="font-body text-sm font-semibold text-on-surface">
                  {generateDateValue}
                </span>
              </div>
            </div>
          </header>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-12 bg-surface-container-lowest border-l-[3px] border-outline-variant/30 pl-6 py-2"
          >
            <span className="block font-label text-[10px] uppercase tracking-widest text-secondary mb-3 font-bold">
              Research Inquiry
            </span>
            <p className="font-headline text-2xl italic text-on-surface/80 leading-relaxed">
              "{selectedAnswer.query}"
            </p>
          </motion.div>

          {selectedAnswer.selectionWarning && (
            <div className="mb-8 p-4 bg-amber-50 border border-amber-300 rounded-sm text-sm text-amber-800">
              Fallback Warning: {selectedAnswer.selectionWarning}
            </div>
          )}

          {selectedAnswer.answer.summary && (
            <div className="mb-12 bg-surface-container-low p-8 rounded-sm editorial-shadow">
              <span className="block font-label text-[10px] uppercase tracking-widest text-primary mb-4 font-bold">
                Answer Summary
              </span>
              <p className="font-body text-lg text-secondary leading-relaxed">
                {selectedAnswer.answer.summary}
              </p>
            </div>
          )}

          <article className="prose prose-slate max-w-none mb-20">
            {renderEssayMarkdown(selectedAnswer.answer.markdown)}
          </article>

          {selectedAnswer.directApiArticle && (
            <section className="mt-16 pt-10 border-t border-outline-variant/15 mb-20">
              <div className="max-w-4xl">
                <span className="block font-label text-[10px] uppercase tracking-[0.2em] text-secondary mb-4 font-bold">
                  Direct API Output
                </span>
                <h3 className="font-headline text-3xl lg:text-4xl font-bold text-on-surface mb-4 leading-tight">
                  纯单次 API 生成结果
                </h3>
                <p className="font-body text-base text-secondary leading-relaxed mb-10">
                  以下内容展示同一问题下，直接单次调用模型生成的文章结果。
                </p>

                {selectedAnswer.directApiArticle.title && (
                  <h4 className="font-headline text-2xl font-bold text-on-surface mb-6 leading-snug">
                    {selectedAnswer.directApiArticle.title}
                  </h4>
                )}

                <article className="prose prose-slate max-w-none">
                  {renderEssayMarkdown(selectedAnswer.directApiArticle.markdown, {
                    muted: true,
                    headingLevel: "h3",
                  })}
                </article>
              </div>
            </section>
          )}

          <section className="pt-10 border-t border-outline-variant/15">
            <div className="flex items-center gap-2 mb-8">
              <Sparkles className="w-4 h-4 text-secondary" />
              <h3 className="font-label text-xs font-bold uppercase tracking-[0.2em] text-secondary">
                Methodological Footprint
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
              <div className="md:col-span-4">
                <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-3">
                  Main Skill
                </span>
                <div className="bg-surface-container-low p-5 rounded-sm border border-outline-variant/10">
                  {selectedAnswer.selectedMainSkillNames.length > 0 ? (
                    <div className="flex flex-wrap gap-2 mb-2">
                      {selectedAnswer.selectedMainSkillNames.map((skill, idx) => (
                        <span
                          key={`${skill}-${idx}`}
                          className="inline-flex items-center gap-2 bg-surface px-3 py-1.5 rounded-sm border border-outline-variant/10"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-outline-variant/40"></span>
                          <span className="font-headline text-sm font-bold text-on-surface">
                            {skill}
                          </span>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="font-headline text-lg font-bold text-on-surface mb-2">
                      {selectedAnswer.selectedMainSkillName || "Unspecified Framework"}
                    </div>
                  )}
                  <div className="font-label text-[9px] uppercase tracking-widest text-outline-variant">
                    {selectedAnswer.selectedMainSkillNames.length > 1
                      ? "Main Skills Applied"
                      : "Main Skill Applied"}
                  </div>
                </div>
              </div>

              <div className="md:col-span-8">
                <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-3">
                  Sub Skills
                </span>
                <div className="flex flex-wrap gap-3">
                  {selectedAnswer.selectedSubSkillNames.length > 0 ? (
                    selectedAnswer.selectedSubSkillNames.map((skill, idx) => (
                      <span
                        key={idx}
                        className="flex items-center gap-2 bg-surface-container-low px-4 py-2.5 rounded-sm border border-outline-variant/10"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-outline-variant/40"></span>
                        <span className="font-body text-xs text-secondary">{skill}</span>
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-outline-variant italic mt-2">
                      No sub skills recorded.
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="pt-8 mt-12 flex items-center justify-between border-t border-outline-variant/15">
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-mono text-outline-variant normal-case tracking-widest">
                  Model Name: {selectedAnswer.modelName || "Unknown"}
                </span>
                <span className="text-[10px] font-mono text-outline-variant normal-case tracking-widest">
                  Api Base: {selectedAnswer.apiBase || "Unknown"}
                </span>
              </div>
            </div>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-grow bg-surface overflow-y-auto custom-scrollbar">
      <div className="px-12 py-12">
        <header className="mb-16">
          <h1 className="font-headline text-5xl font-light text-on-surface mb-6 tracking-tight leading-tight">
            Synthesize an economic perspective through academic rigor.
          </h1>
          <p className="font-body text-lg text-secondary max-w-5xl leading-relaxed">
            Trigger backend answer jobs and read answer_json outputs with selected skill traceability.
          </p>
        </header>

        <div className="bg-surface-container-low p-10 rounded-sm editorial-shadow">
          <div className="space-y-10">
            <div className="space-y-4">
              <label className="block font-label text-xs font-bold text-on-surface-variant uppercase tracking-widest">
                Select Author
              </label>
              <div className="relative group">
                <select
                  value={selectedAuthorId || ""}
                  onChange={(event) => onSelectAuthor(event.target.value)}
                  className="w-full appearance-none bg-surface-container-lowest border-b border-outline-variant/20 focus:border-primary px-4 py-4 pr-10 outline-none font-headline text-2xl transition-all cursor-pointer"
                >
                  <option value="" disabled>
                    Select an author
                  </option>
                  {authors.map((author) => (
                    <option key={author.authorId} value={author.authorId}>
                      {author.authorName}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-secondary pointer-events-none w-6 h-6" />
              </div>
            </div>

            <div className="space-y-4">
              <label className="block font-label text-xs font-bold text-on-surface-variant uppercase tracking-widest">
                Define Query
              </label>
              <div className="bg-surface-container-lowest p-8 border-b-2 border-outline-variant/15 focus-within:border-primary transition-colors">
                <textarea
                  value={query}
                  onChange={(event) => onQueryChange(event.target.value)}
                  className="w-full bg-transparent border-none focus:ring-0 font-headline text-3xl leading-snug placeholder:text-outline-variant/40 resize-none outline-none"
                  placeholder="e.g., The implications of digital currency on central bank sovereignty..."
                  rows={4}
                />
              </div>
            </div>

            {showRunningProgress && runningJob && (
              <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-sm p-6">
                <div className="flex items-center justify-between gap-4 mb-4">
                  <span className="font-label text-[10px] uppercase tracking-widest text-secondary">
                    Job Progress
                  </span>
                  <span className="font-label text-[10px] uppercase tracking-widest text-primary">
                    {runningProgress}%
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                      Status
                    </span>
                    <span className="font-body text-sm font-semibold text-on-surface">
                      {formatJobStatus(runningJob.status)}
                    </span>
                  </div>
                  <div>
                    <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                      Stage
                    </span>
                    <span className="font-body text-sm font-semibold text-on-surface">
                      {formatJobStage(runningJob.currentStage)}
                    </span>
                  </div>
                </div>
                <div className="h-2 bg-surface-container-low rounded-sm overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${runningProgress}%` }}
                  />
                </div>
              </div>
            )}

            {runningJob && !showRunningProgress && (
              <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-sm px-4 py-3 text-sm text-secondary">
                {runningJob.status === "success"
                  ? "Generation completed. Loading result..."
                  : `Generation ${runningJob.status}. ${runningJob.errorMessage || ""}`.trim()}
              </div>
            )}

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pt-4">
              <div className="flex flex-col sm:flex-row sm:items-center gap-6">
                <div className="flex items-center text-xs font-label text-secondary gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary fill-primary/20" />
                  <span>Archive Access Verified</span>
                </div>
                <div className="flex items-center text-xs font-label text-secondary gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary fill-primary/20" />
                  <span>Output: answer_json</span>
                </div>
              </div>
              <button
                onClick={onGenerate}
                disabled={!selectedAuthorId || !query.trim() || creating}
                className="flex items-center justify-center gap-4 bg-primary text-on-primary px-10 py-5 rounded-sm hover:bg-primary-dim transition-all shadow-xl shadow-primary/10 group disabled:opacity-60"
              >
                <span className="font-label text-sm font-bold uppercase tracking-widest">
                  {creating ? "Generating..." : "Generate Article"}
                </span>
                <Sparkles className="w-5 h-5 group-hover:rotate-12 transition-transform" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
