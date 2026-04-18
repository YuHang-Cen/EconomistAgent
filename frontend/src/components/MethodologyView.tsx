import { ChevronRight, Download, Sparkles } from "lucide-react";
import type { Author, Job } from "../types";
import { useMemo, useState } from "react";

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
  onGenerate: () => Promise<void> | void;
  onRefresh: () => Promise<void> | void;
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
  onGenerate,
  onRefresh,
}: MethodologyViewProps) {
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
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

  return (
    <div className="flex-grow bg-background p-8 lg:p-12 overflow-y-auto custom-scrollbar">
      <section className="mb-10">
        <nav className="text-[10px] uppercase tracking-widest text-secondary font-bold mb-2 flex items-center gap-2">
          <span>Methodology</span>
          <ChevronRight className="w-2.5 h-2.5" />
          <span className="text-primary">{selectedAuthor?.authorName || "No Author Selected"}</span>
        </nav>
        <h1 className="text-5xl lg:text-6xl font-headline font-medium text-on-background leading-tight">
          Methodology & Intellectual Frameworks
        </h1>
      </section>

      <section className="flex items-center gap-3 mb-6">
        <button
          disabled={!selectedAuthor || generating}
          onClick={onGenerate}
          className="bg-primary text-on-primary px-6 py-2 rounded-sm font-label text-xs tracking-widest uppercase hover:bg-primary-dim transition-all shadow-md disabled:opacity-60"
        >
          {generating ? "Generating..." : "Generate Skills"}
        </button>
        <button
          disabled={!selectedAuthor}
          onClick={onRefresh}
          className="border border-outline-variant/20 px-6 py-2 rounded-sm font-label text-xs tracking-widest uppercase hover:bg-surface-container-low transition-all disabled:opacity-60"
        >
          Refresh Latest
        </button>
        {runningJob && (
          <span className="text-xs text-secondary">
            Job: {runningJob.status} / stage {runningJob.currentStage || "-"} / progress {runningJob.progress}%
          </span>
        )}
      </section>

      {!outputs ? (
        <div className="py-12 px-6 text-center border-2 border-dashed border-outline-variant/10 rounded-sm">
          <p className="text-sm text-secondary italic font-body">
            No skill snapshot found for this author yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="space-y-8 lg:col-span-4">
            <div className="bg-surface-container-low p-6 rounded-sm editorial-shadow">
              <h3 className="text-xl font-headline font-semibold mb-4">Main Skills</h3>
              <div className="space-y-2">
                {mainSkills.length === 0 && <p className="text-xs text-secondary italic">No main skills.</p>}
                {mainSkills.map((skill, index) => {
                  const sectionId = String(skill.section_id || "");
                  const pattern = (skill.pattern_summary || {}) as Record<string, unknown>;
                  const name = String(pattern.name || skill.section_title || `main_${index + 1}`);
                  const active = selectedSection === sectionId;
                  return (
                    <button
                      key={`${sectionId}-${String(skill.main_skill_id || index)}`}
                      onClick={() => setSelectedSectionId(sectionId)}
                      className={`w-full text-left p-3 rounded-sm border transition-all ${
                        active ? "border-primary bg-primary/5 text-primary" : "border-outline-variant/20 hover:bg-white"
                      }`}
                    >
                      <div className="text-sm font-semibold">{name}</div>
                      <div className="text-[10px] text-secondary">section: {sectionId}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="bg-surface-container-low p-6 rounded-sm editorial-shadow">
              <h3 className="text-xl font-headline font-semibold mb-4">Sub Skills</h3>
              <div className="space-y-2">
                {selectedSubSkills.length === 0 && <p className="text-xs text-secondary italic">No sub skills for selected section.</p>}
                {selectedSubSkills.map((item, index) => (
                  <div key={`${String(item.main_skill_id || "sub")}-${index}`} className="p-3 rounded-sm border border-outline-variant/20 bg-white">
                    <div className="text-sm font-semibold">{String(item.name || "Unnamed Sub Skill")}</div>
                    <div className="text-[10px] text-secondary">{String(item.normalized_pattern || "")}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-8 space-y-6">
            <div className="bg-white shadow-2xl p-8 border-t-4 border-primary rounded-sm custom-scrollbar">
              <div className="flex items-center gap-3 mb-4">
                <Sparkles className="w-5 h-5 text-primary" />
                <h3 className="font-headline text-2xl font-bold text-on-background">Selected Main Skill</h3>
              </div>

              {selectedMain ? (
                <div className="space-y-4">
                  <pre className="text-xs bg-surface-container-low p-4 rounded-sm overflow-x-auto whitespace-pre-wrap">
                    {selectedMainMarkdown?.markdown
                      ? String(selectedMainMarkdown.markdown)
                      : JSON.stringify(selectedMain, null, 2)}
                  </pre>
                  {selectedSubMarkdown.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold mb-2">Sub Skills Markdown</h4>
                      <div className="space-y-3">
                        {selectedSubMarkdown.map((item, index) => (
                          <pre key={`${String(item.file_name || index)}`} className="text-xs bg-surface-container-low p-4 rounded-sm overflow-x-auto whitespace-pre-wrap">
                            {String(item.markdown || "")}
                          </pre>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-secondary italic">Select one main skill to inspect details.</p>
              )}

              <div className="pt-6 mt-6 flex items-center justify-between border-t border-outline-variant/10">
                <span className="text-[10px] text-outline-variant">Source: backend outputs</span>
                <button className="flex items-center gap-2 text-primary font-label text-[10px] uppercase tracking-widest font-bold hover:underline">
                  <Download className="w-4 h-4" /> Export via API
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
