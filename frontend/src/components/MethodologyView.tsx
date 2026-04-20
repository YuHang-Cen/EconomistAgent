import { ChevronRight, Download, Terminal, Trash2 } from "lucide-react";
import type { Author, Job } from "../types";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import React from "react";

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

// 辅助组件：渲染小标题
function formatJobStatus(value: string | null | undefined): string {
  const text = (value || "queued").trim().toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatJobStage(value: string | null | undefined): string {
  const normalized = (value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    analyze: "Analyze",
    main_skill: "Main Skill",
    sub_skill: "Sub Skill",
    render: "Render",
    select_skills: "Select Skills",
    answer: "Answer",
    extract: "Extract",
    segment_sync: "Segment Sync",
  };
  return labels[normalized] || "Pending";
}

function normalizeProgress(value: number | null | undefined): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

const SectionHeader = ({ title }: { title: string }) => (
  <div className="flex items-center gap-2 mb-4 mt-10 text-[11px] font-bold tracking-[0.15em] text-secondary uppercase">
    <div className="w-1 h-1 rounded-full bg-secondary"></div>
    {title}
  </div>
);

// 辅助组件：渲染有序步骤列表
const ExecutionSkeletonList = ({ steps }: { steps: any[] }) => (
  <ol className="space-y-4">
    {steps.map((step, idx) => (
      <li key={idx} className="flex gap-4 items-start">
        <span className="flex-shrink-0 w-7 h-7 rounded-full bg-surface-container-low flex items-center justify-center text-xs font-bold text-secondary">
          {idx + 1}
        </span>
        <span className="text-sm text-secondary pt-1 leading-relaxed">{String(step)}</span>
      </li>
    ))}
  </ol>
);

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
  const showRunningProgress =
    !!runningJob && (runningJob.status === "queued" || runningJob.status === "running");
  const showTerminalHint =
    !!runningJob && (runningJob.status === "failed" || runningJob.status === "canceled");
  const runningProgress = normalizeProgress(runningJob?.progress);

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

  // Main Skill 提取字段
  const mainPattern = (selectedMain?.pattern_summary || {}) as Record<string, unknown>;
  const mainName = String(mainPattern.name || selectedMain?.section_title || "Unnamed Skill");
  const mainDescription = String(mainPattern.description || "");
  const mainApplicability = String(mainPattern.applicability || "");
  const mainMethodProgram = String(mainPattern.chapter_method_summary || "");
  const mainCoreSteps = Array.isArray(mainPattern.core_steps) ? mainPattern.core_steps : [];
  const mainPatternFlow = Array.isArray(mainPattern.pattern_flow) ? mainPattern.pattern_flow : [];

  // Sub Skill 提取字段
  const currentSub = selectedSubSkills[selectedSubSkillIndex] || {};
  const subName = String(currentSub.name || "Unnamed Sub Skill");
  const subDescription = String(currentSub.description || "");
  const subMethodProgram = String(currentSub.method_program_summary || "");
  const subActionChain = Array.isArray(currentSub.abstract_action_chain) ? currentSub.abstract_action_chain : [];

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

      {showRunningProgress && runningJob && (
        <section className="mb-10 bg-surface-container-low border border-outline-variant/20 rounded-sm p-6">
          <div className="flex items-center justify-between gap-4 mb-4">
            <span className="font-label text-[10px] uppercase tracking-widest text-secondary">
              Job Progress
            </span>
            <span className="font-label text-[10px] uppercase tracking-widest text-primary">
              {runningProgress}%
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                Status
              </span>
              <span className="font-body text-sm font-semibold text-on-surface">
                {formatJobStatus(runningJob.status)}
              </span>
            </div>
            <div className="md:col-span-2">
              <span className="block font-label text-[9px] uppercase tracking-widest text-outline-variant mb-2">
                Stage
              </span>
              <span className="font-body text-sm font-semibold text-on-surface">
                {formatJobStage(runningJob.currentStage)}
              </span>
            </div>
          </div>
          <div className="h-2 bg-surface-container-high rounded-sm overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${runningProgress}%` }}
            />
          </div>
        </section>
      )}

      {showTerminalHint && runningJob && (
        <section className="mb-10 bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-3 text-sm text-secondary">
          {`Task ${runningJob.status}. ${runningJob.errorMessage || ""}`.trim()}
        </section>
      )}

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
                className="bg-white shadow-2xl border border-outline-variant/20 rounded-sm relative"
              >
                {/* 顶部指示条 */}
                <div className="h-1 w-full bg-primary rounded-t-sm"></div>
                
                <div className="p-10 lg:p-14">
                  {/* 标题区域 */}
                  <div className="flex items-start justify-between mb-8 gap-4">
                    <div className="flex gap-4 items-center">
                      <div className="w-14 h-14 bg-surface-container-low border border-outline-variant/20 flex items-center justify-center rounded-sm text-secondary flex-shrink-0">
                        <Terminal className="w-6 h-6" />
                      </div>
                      <div>
                        <h2 className="font-headline text-3xl font-bold text-on-background leading-tight">
                          {activeTab === "main" ? mainName : subName}
                        </h2>
                        <p className="text-[10px] font-bold tracking-[0.2em] uppercase text-secondary mt-2">
                          {activeTab === "main" ? "MAIN SKILL" : "SUB SKILL"}
                        </p>
                      </div>
                    </div>
                    {/* 右上角的虚化文字修饰 */}
                    <div className="text-4xl font-headline font-black text-outline-variant/10 select-none">
                      {activeTab === "main" ? "#MS" : "#SS"}
                    </div>
                  </div>

                  {activeTab === "main" && selectedMain ? (
                    // ================== Main Skill 视图 ==================
                    <div className="space-y-10">
                      {mainDescription && (
                        <div>
                          <SectionHeader title="Skill Summary" />
                          <div className="font-headline text-xl text-on-background leading-relaxed border-l-4 border-primary pl-5 py-1">
                            "{mainDescription}"
                          </div>
                        </div>
                      )}

                      {mainApplicability && (
                        <div>
                          <SectionHeader title="When to Use" />
                          <div className="bg-surface-container-low p-6 rounded-sm text-sm text-secondary leading-relaxed border border-outline-variant/10">
                            {mainApplicability}
                          </div>
                        </div>
                      )}

                      {mainMethodProgram && (
                        <div>
                          <SectionHeader title="Method Program" />
                          <div className="bg-surface-container-low p-6 rounded-sm text-sm text-secondary leading-relaxed border border-outline-variant/10">
                            {mainMethodProgram}
                          </div>
                        </div>
                      )}

                      {mainCoreSteps.length > 0 && (
                        <div>
                          <SectionHeader title="Execution Skeleton" />
                          <ExecutionSkeletonList steps={mainCoreSteps} />
                        </div>
                      )}

                      {mainPatternFlow.length > 0 && (
                        <div>
                          <SectionHeader title="Pattern Flow" />
                          <div className="flex flex-wrap items-center gap-2">
                            {mainPatternFlow.map((flowItem, idx) => (
                              <React.Fragment key={idx}>
                                <span className="bg-[#2b2b2b] text-white px-3 py-2 rounded-sm text-[10px] font-bold uppercase tracking-widest">
                                  {String(flowItem)}
                                </span>
                                {idx < mainPatternFlow.length - 1 && (
                                  <span className="text-outline-variant">
                                    <ChevronRight className="w-4 h-4" />
                                  </span>
                                )}
                              </React.Fragment>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : activeTab === "sub" && selectedSubSkills[selectedSubSkillIndex] ? (
                    // ================== Sub Skill 视图 ==================
                    <div className="space-y-10">
                      {subDescription && (
                        <div>
                          <SectionHeader title="Skill Summary" />
                          <div className="font-headline text-xl text-on-background leading-relaxed border-l-4 border-primary pl-5 py-1">
                            "{subDescription}"
                          </div>
                        </div>
                      )}

                      {subMethodProgram && (
                        <div>
                          <SectionHeader title="Method Program" />
                          <div className="bg-surface-container-low p-6 rounded-sm text-sm text-secondary leading-relaxed border border-outline-variant/10">
                            {subMethodProgram}
                          </div>
                        </div>
                      )}

                      {subActionChain.length > 0 && (
                        <div>
                          <SectionHeader title="Execution Skeleton" />
                          <ExecutionSkeletonList steps={subActionChain} />
                        </div>
                      )}
                    </div>
                  ) : (
                    // ================== 兜底空状态 ==================
                    <p className="italic text-secondary py-10">Awaiting selection...</p>
                  )}
                  
                  <div className="pt-8 mt-12 flex items-center justify-between border-t border-outline-variant/10">
                    <span className="text-[10px] font-mono text-outline-variant uppercase tracking-widest">Source: Extracted Core</span>
                    <button className="flex items-center gap-2 text-primary font-label text-[10px] uppercase tracking-widest font-bold hover:underline group">
                      <Download className="w-4 h-4 transition-transform group-hover:translate-y-0.5" /> Export Data
                    </button>
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
