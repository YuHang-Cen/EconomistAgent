import { ChevronRight, Download, Sparkles, Terminal, Trash2 } from "lucide-react";
import type { Author, Job } from "../types";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";

interface SkillOutputs {
  mainSkillJson: Record<string, unknown> | null;
  subSkillJson: Record<string, unknown> | null;
  mainSkillsMdJson: Array<Record<string, unknown>>;
  subSkillsMdJson: Array<Record<string, unknown>>;
}

interface MethodologyViewProps {
  selectedAuthor: Author | null;
  runningJob: Job | null;
  outputs: SkillOutputs | null;
  generating: boolean;
  deletingSectionId: string | null;
  onGenerate: () => Promise<void> | void;
  onRefresh: () => Promise<void> | void;
  onDeleteMainSkill: (sectionId: string) => Promise<void> | void;
}

function readMainSkills(outputs: SkillOutputs | null): Array<Record<string, unknown>> {
  const list = outputs?.mainSkillJson?.main_skills;
  return Array.isArray(list) ? list.filter((item): item is Record<string, unknown> => !!item && typeof item === "object") : [];
}

function readSubSkills(outputs: SkillOutputs | null): Array<Record<string, unknown>> {
  const list = outputs?.subSkillJson?.sub_skills;
  return Array.isArray(list) ? list.filter((item): item is Record<string, unknown> => !!item && typeof item === "object") : [];
}

export default function MethodologyView({
  selectedAuthor,
  runningJob,
  outputs,
  generating,
  deletingSectionId,
  onGenerate,
  onRefresh,
  onDeleteMainSkill,
}: MethodologyViewProps) {
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"main" | "sub">("main");
  const [selectedSubSkillIndex, setSelectedSubSkillIndex] = useState<number>(0);

  const mainSkills = useMemo(() => readMainSkills(outputs), [outputs]);
  const subSkills = useMemo(() => readSubSkills(outputs), [outputs]);

  const selectedMain = useMemo(() => {
    const section = selectedSectionId || (typeof mainSkills[0]?.section_id === "string" ? String(mainSkills[0].section_id) : null);
    if (!section) return null;
    return mainSkills.find((item) => String(item.section_id || "") === section) || null;
  }, [mainSkills, selectedSectionId]);

  const selectedSection = selectedMain ? String(selectedMain.section_id || "") : null;
  const selectedSubSkills = selectedSection
    ? subSkills.filter((item) => String(item.section_id || "") === selectedSection)
    : [];

  const selectedMainMarkdown = selectedSection
    ? outputs?.mainSkillsMdJson.find((item) => String(item.section_id || "") === selectedSection)
    : null;
  const selectedSubMarkdown = selectedSection
    ? outputs?.subSkillsMdJson.filter((item) => String(item.section_id || "") === selectedSection)
    : [];

  useEffect(() => {
    if (!selectedSectionId) return;
    const stillExists = mainSkills.some(
      (item) => String(item.section_id || "") === selectedSectionId
    );
    if (stillExists) return;
    const fallback = mainSkills[0];
    const fallbackSectionId =
      fallback && fallback.section_id !== undefined && fallback.section_id !== null
        ? String(fallback.section_id)
        : null;
    setSelectedSectionId(fallbackSectionId);
    setActiveTab("main");
    setSelectedSubSkillIndex(0);
  }, [mainSkills, selectedSectionId]);

  return (
    <div className="flex-grow bg-background p-8 lg:p-12 overflow-y-auto custom-scrollbar">
      <section className="mb-10">
        <nav className="text-[10px] uppercase tracking-widest text-secondary font-bold mb-2 flex items-center gap-2">
          <span>Methodology</span>
          <ChevronRight className="w-2.5 h-2.5" />
          <span className="text-primary">{selectedAuthor?.authorName || "No Author Selected"}</span>
        </nav>
        <h1 className="text-5xl lg:text-6xl font-headline font-medium text-on-background leading-tight">
          Methodology & <span className="italic">Intellectual</span> Frameworks
        </h1>
      </section>

      <section className="flex items-center gap-3 mb-12">
        <button
          disabled={!selectedAuthor || generating}
          onClick={onGenerate}
          className="bg-primary text-on-primary px-8 py-3 rounded-sm font-label text-xs tracking-widest uppercase hover:bg-primary-dim transition-all shadow-lg shadow-primary/20 disabled:opacity-60"
        >
          {generating ? "Generating..." : "Generate Skills"}
        </button>
        <button
          disabled={!selectedAuthor}
          onClick={onRefresh}
          className="border border-outline-variant/30 px-8 py-3 rounded-sm font-label text-xs tracking-widest uppercase hover:bg-surface-container-low transition-all disabled:opacity-60"
        >
          Refresh Latest
        </button>
      </section>

      {!outputs ? (
        <div className="py-20 px-6 text-center border-2 border-dashed border-outline-variant/20 rounded-sm bg-surface-container-low/30">
          <p className="text-sm text-secondary italic font-body">
            No skill snapshot found for this author yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
          {/* 左侧选择面板 */}
          <div className="space-y-10 lg:col-span-4">
            {/* Main Skills 列表 */}
            <section>
              <h3 className="text-xs font-label text-primary uppercase tracking-[0.2em] mb-6 font-bold">Main Skills</h3>
              <div className="space-y-3">
                {mainSkills.map((skill, index) => {
                  const sectionId = String(skill.section_id || "");
                  const pattern = (skill.pattern_summary || {}) as Record<string, unknown>;
                  const name = String(pattern.name || skill.section_title || `main_${index + 1}`);
                  const isActive = selectedSection === sectionId && activeTab === "main";
                  const deleting = deletingSectionId === sectionId;

                  return (
                    <motion.div
                      key={sectionId}
                      whileHover={{ x: 4 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => {
                        setSelectedSectionId(sectionId);
                        setActiveTab("main");
                        setSelectedSubSkillIndex(0);
                      }}
                      className={`w-full flex items-center justify-between cursor-pointer text-left p-5 rounded-sm transition-all border-l-4 editorial-shadow group ${
                        isActive
                          ? "bg-white border-primary shadow-lg"
                          : "bg-surface-container-low border-transparent hover:bg-white text-secondary hover:text-on-background"
                      }`}
                    >
                      <div className="font-headline text-lg font-bold leading-tight pr-4">{name}</div>
                      
                      {/* 删除按钮 */}
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          if (deleting) return;
                          await onDeleteMainSkill(sectionId);
                        }}
                        disabled={deleting}
                        className={`p-2 rounded-sm transition-all flex-shrink-0 ${
                          isActive
                            ? "text-outline-variant hover:text-red-500 hover:bg-red-50"
                            : "text-transparent group-hover:text-outline-variant hover:!text-red-500 hover:!bg-red-50"
                        } ${deleting ? "opacity-60 cursor-not-allowed" : ""}`}
                        title={deleting ? "Deleting..." : "Delete Main Skill"}
                      >
                        <Trash2 className={`w-[18px] h-[18px] ${deleting ? "animate-pulse" : ""}`} />
                      </button>
                    </motion.div>
                  );
                })}
              </div>
            </section>

            {/* Sub Skills 列表 */}
            <section>
              <h3 className="text-xs font-label text-primary uppercase tracking-[0.2em] mb-6 font-bold">Sub-Competencies</h3>
              <div className="space-y-3">
                {selectedSubSkills.length === 0 ? (
                  <p className="text-[10px] text-outline-variant italic uppercase tracking-widest">Select a main skill to reveal sub-patterns.</p>
                ) : (
                  selectedSubSkills.map((item, index) => {
                    const isActive = activeTab === "sub" && selectedSubSkillIndex === index;
                    return (
                      <motion.button
                        key={index}
                        whileHover={{ x: 4 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => {
                          setActiveTab("sub");
                          setSelectedSubSkillIndex(index);
                        }}
                        className={`w-full text-left p-5 rounded-sm transition-all border-l-4 editorial-shadow ${
                          isActive
                            ? "bg-white border-primary shadow-lg"
                            : "bg-surface-container-low border-transparent hover:bg-white text-secondary hover:text-on-background"
                        }`}
                      >
                        <div className="font-headline text-base font-bold mb-1">{String(item.name || "Unnamed Skill")}</div>
                        <div className="text-[10px] font-label uppercase tracking-widest opacity-60">
                          {String(item.normalized_pattern || "Standard Pattern")}
                        </div>
                      </motion.button>
                    );
                  })
                )}
              </div>
            </section>
          </div>

          {/* 右侧详情面板 */}
          <div className="lg:col-span-8 sticky top-32">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab === "main" ? selectedSection : `${selectedSection}-${selectedSubSkillIndex}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="bg-white shadow-2xl p-10 border-t-4 border-primary rounded-sm relative"
              >
                <div className="flex items-center gap-4 mb-10">
                  <div className="w-12 h-12 bg-primary/10 flex items-center justify-center rounded-sm">
                    <Terminal className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-headline text-2xl font-bold text-on-background">
                      {activeTab === "main" ? "Primary Framework" : "Tactical Heuristic"}
                    </h3>
                    <p className="text-[10px] font-label text-primary tracking-[0.2em] uppercase font-bold">Extracted Logic Module</p>
                  </div>
                </div>

                <div className="prose prose-slate max-w-none">
                  {activeTab === "main" ? (
                    selectedMain ? (
                      <div className="bg-surface-container-low/50 p-8 rounded-sm border border-outline-variant/10 font-body text-sm leading-relaxed text-secondary italic">
                        {selectedMainMarkdown?.markdown ? String(selectedMainMarkdown.markdown) : "Parsing core logic..."}
                      </div>
                    ) : (
                      <p className="italic text-secondary">Awaiting framework selection.</p>
                    )
                  ) : (
                    selectedSubSkills[selectedSubSkillIndex] ? (
                      <div className="bg-surface-container-low/50 p-8 rounded-sm border border-outline-variant/10 font-body text-sm leading-relaxed text-secondary italic">
                        {selectedSubMarkdown[selectedSubSkillIndex]?.markdown ? String(selectedSubMarkdown[selectedSubSkillIndex].markdown) : "Parsing sub-competency..."}
                      </div>
                    ) : (
                      <p className="italic text-secondary">Awaiting sub-skill identification.</p>
                    )
                  )}
                </div>

                <div className="pt-8 mt-12 flex items-center justify-between border-t border-outline-variant/10">
                  <span className="text-[10px] font-mono text-outline-variant uppercase tracking-widest">Stability: v2.4.0-STABLE</span>
                  <button className="flex items-center gap-2 text-primary font-label text-[10px] uppercase tracking-widest font-bold hover:underline group">
                    <Download className="w-4 h-4 transition-transform group-hover:translate-y-0.5" /> Export Module
                  </button>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}

