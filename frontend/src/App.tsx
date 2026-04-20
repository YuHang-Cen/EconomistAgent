import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createAnswerJob,
  createAuthor,
  createSkillsJob,
  deleteMainSkillSection,
  deleteAuthorAnswerJob,
  deleteAuthor,
  deleteChapter,
  deleteSegment,
  getOutput,
  listAuthorJobs,
  listAuthors,
  listChapters,
  listDocuments,
  listOutputs,
  listSegments,
  mapApiErrorToUi,
  pollJob,
  reloadDocument,
  updateAuthor,
  uploadAuthorAvatar,
  uploadDocumentFile,
} from "./api";
import type { AnswerVM, Author, Chapter, Job, ModelConfig, Segment } from "./types";
import { parseAnswerJson } from "./api/outputParser";
import AnalysisSidebar from "./components/AnalysisSidebar";
import AnalysisView from "./components/AnalysisView";
import AuthorSection from "./components/AuthorSection";
import CreateAuthorModal from "./components/CreateAuthorModal";
import LandingPage from "./components/LandingPage";
import MethodologySidebar from "./components/MethodologySidebar";
import MethodologyView from "./components/MethodologyView";
import Navbar from "./components/Navbar";
import SegmentSidebar from "./components/SegmentSidebar";
import SegmentView from "./components/SegmentView";
import SettingsModal, { RuntimeSettingsState } from "./components/SettingsModal";
import Sidebar from "./components/Sidebar";

type Tab = "archive" | "analysis" | "methodology" | "answer" | "landing";

interface SkillOutputs {
  mainSkillJson: Record<string, unknown> | null;
  subSkillJson: Record<string, unknown> | null;
  mainSkillsMdJson: Array<Record<string, unknown>>;
  subSkillsMdJson: Array<Record<string, unknown>>;
}

interface SegmentSnapshot {
  chapters: Chapter[];
  segments: Segment[];
}

const EMPTY_SETTINGS: RuntimeSettingsState = {
  skillsModel: {
    provider: "",
    modelName: "",
    apiBase: "",
    apiKey: "",
  },
  answerModel: {
    provider: "",
    modelName: "",
    apiBase: "",
    apiKey: "",
  },
};

function toModelConfigOrUndefined(model: RuntimeSettingsState["skillsModel"]): ModelConfig | undefined {
  const next: ModelConfig = {};
  if (model.provider.trim()) next.provider = model.provider.trim();
  if (model.modelName.trim()) next.modelName = model.modelName.trim();
  if (model.apiBase.trim()) next.apiBase = model.apiBase.trim();
  if (model.apiKey.trim()) next.apiKey = model.apiKey.trim();
  return Object.keys(next).length > 0 ? next : undefined;
}

function getJobById(history: Record<string, Job[]>, authorId: string | null, jobId: string | null): Job | null {
  if (!authorId || !jobId) return null;
  const jobs = history[authorId] || [];
  return jobs.find((item) => item.jobId === jobId) || null;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("landing");
  const [isCreateAuthorOpen, setCreateAuthorOpen] = useState(false);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettingsState>(EMPTY_SETTINGS);

  const [authors, setAuthors] = useState<Author[]>([]);
  const [documentsByAuthor, setDocumentsByAuthor] = useState<Record<string, Array<any>>>({});
  const [loadingDocumentsByAuthor, setLoadingDocumentsByAuthor] = useState<Record<string, boolean>>({});

  const [creatingAuthor, setCreatingAuthor] = useState(false);
  const [deletingAuthorId, setDeletingAuthorId] = useState<string | null>(null);
  const [avatarUploadingAuthorId, setAvatarUploadingAuthorId] = useState<string | null>(null);
  const [renameSavingAuthorId, setRenameSavingAuthorId] = useState<string | null>(null);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [reloadingDocumentId, setReloadingDocumentId] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [selectedArchiveAuthorId, setSelectedArchiveAuthorId] = useState<string | null>(null);

  const [selectedSegmentAuthorId, setSelectedSegmentAuthorId] = useState<string | null>(null);
  const [selectedSegmentDocumentId, setSelectedSegmentDocumentId] = useState<string | null>(null);
  const [selectedSegmentChapterId, setSelectedSegmentChapterId] = useState<string | null>(null);
  const [chaptersByDocument, setChaptersByDocument] = useState<Record<string, Chapter[]>>({});
  const [segments, setSegments] = useState<Segment[]>([]);
  const [segmentHistory, setSegmentHistory] = useState<SegmentSnapshot[]>([{ chapters: [], segments: [] }]);
  const [segmentHistoryIndex, setSegmentHistoryIndex] = useState(0);

  const [selectedMethodologyAuthorId, setSelectedMethodologyAuthorId] = useState<string | null>(null);
  const [methodologyRunningJob, setMethodologyRunningJob] = useState<Job | null>(null);
  const [methodologyOutputs, setMethodologyOutputs] = useState<SkillOutputs | null>(null);
  const [methodologyGenerating, setMethodologyGenerating] = useState(false);
  const [methodologyDeletingSectionId, setMethodologyDeletingSectionId] = useState<string | null>(null);

  const [selectedAnalysisAuthorId, setSelectedAnalysisAuthorId] = useState<string | null>(null);
  const [analysisHistoryByAuthor, setAnalysisHistoryByAuthor] = useState<Record<string, Job[]>>({});
  const [analysisLoadingByAuthor, setAnalysisLoadingByAuthor] = useState<Record<string, boolean>>({});
  const [selectedAnswerJobId, setSelectedAnswerJobId] = useState<string | null>(null);
  const [answersByJob, setAnswersByJob] = useState<Record<string, AnswerVM>>({});
  const [answerQuery, setAnswerQuery] = useState("");
  const [answerCreating, setAnswerCreating] = useState(false);
  const [analysisRunningJob, setAnalysisRunningJob] = useState<Job | null>(null);
  const [deletingAnswerJobId, setDeletingAnswerJobId] = useState<string | null>(null);

  const currentSegmentAuthor = useMemo(
    () => authors.find((item) => item.authorId === selectedSegmentAuthorId) || null,
    [authors, selectedSegmentAuthorId]
  );
  const currentSegmentDocument = useMemo(() => {
    if (!selectedSegmentAuthorId || !selectedSegmentDocumentId) return null;
    return (documentsByAuthor[selectedSegmentAuthorId] || []).find(
      (item) => item.documentId === selectedSegmentDocumentId
    ) || null;
  }, [documentsByAuthor, selectedSegmentAuthorId, selectedSegmentDocumentId]);
  const currentSegmentChapters = useMemo(
    () => (selectedSegmentDocumentId ? chaptersByDocument[selectedSegmentDocumentId] || [] : []),
    [chaptersByDocument, selectedSegmentDocumentId]
  );
  const currentSegmentChapter = useMemo(
    () => currentSegmentChapters.find((item) => item.chapterId === selectedSegmentChapterId) || null,
    [currentSegmentChapters, selectedSegmentChapterId]
  );

  const selectedMethodologyAuthor = useMemo(
    () => authors.find((item) => item.authorId === selectedMethodologyAuthorId) || null,
    [authors, selectedMethodologyAuthorId]
  );
  const selectedAnalysisAuthor = useMemo(
    () => authors.find((item) => item.authorId === selectedAnalysisAuthorId) || null,
    [authors, selectedAnalysisAuthorId]
  );
  const selectedAnswer = selectedAnswerJobId ? answersByJob[selectedAnswerJobId] || null : null;
  const selectedAnswerJob = getJobById(analysisHistoryByAuthor, selectedAnalysisAuthorId, selectedAnswerJobId);

  const handleError = useCallback((error: unknown) => {
    const ui = mapApiErrorToUi(error);
    setGlobalError(`${ui.title}: ${ui.message}`);
  }, []);

  const resetSegmentHistory = useCallback((chapters: Chapter[], nextSegments: Segment[]) => {
    setSegmentHistory([{ chapters, segments: nextSegments }]);
    setSegmentHistoryIndex(0);
  }, []);

  const pushSegmentHistory = useCallback((chapters: Chapter[], nextSegments: Segment[]) => {
    setSegmentHistory((prev) => {
      const sliced = prev.slice(0, segmentHistoryIndex + 1);
      sliced.push({ chapters, segments: nextSegments });
      return sliced;
    });
    setSegmentHistoryIndex((prev) => prev + 1);
  }, [segmentHistoryIndex]);

  const refreshAuthors = useCallback(async () => {
    const items = await listAuthors();
    setAuthors(items);
    if (!selectedArchiveAuthorId && items[0]) setSelectedArchiveAuthorId(items[0].authorId);
    if (!selectedSegmentAuthorId && items[0]) setSelectedSegmentAuthorId(items[0].authorId);
    if (!selectedMethodologyAuthorId && items[0]) setSelectedMethodologyAuthorId(items[0].authorId);
    if (!selectedAnalysisAuthorId && items[0]) setSelectedAnalysisAuthorId(items[0].authorId);
  }, [selectedArchiveAuthorId, selectedSegmentAuthorId, selectedMethodologyAuthorId, selectedAnalysisAuthorId]);

  const ensureDocumentsLoaded = useCallback(
    async (authorId: string, force = false) => {
      if (!force && documentsByAuthor[authorId]) return;
      if (loadingDocumentsByAuthor[authorId]) return;
      setLoadingDocumentsByAuthor((prev) => ({ ...prev, [authorId]: true }));
      try {
        const docs = await listDocuments(authorId);
        setDocumentsByAuthor((prev) => ({ ...prev, [authorId]: docs }));
      } finally {
        setLoadingDocumentsByAuthor((prev) => ({ ...prev, [authorId]: false }));
      }
    },
    [documentsByAuthor, loadingDocumentsByAuthor]
  );

  const syncSegmentView = useCallback(
    async (
      authorId: string, 
      documentId: string, 
      preferredChapterId?: string | null,
      shouldResetHistory = true // 1. 增加此控制参数，默认为开启重置
    ) => {
      const chapters = await listChapters(authorId, documentId);
      setChaptersByDocument((prev) => ({ ...prev, [documentId]: chapters }));
      const chapterId =
        preferredChapterId && chapters.some((item) => item.chapterId === preferredChapterId)
          ? preferredChapterId
          : chapters[0]?.chapterId || null;
      setSelectedSegmentChapterId(chapterId);
      if (!chapterId) {
        setSegments([]);
        if (shouldResetHistory) resetSegmentHistory(chapters, []); // 2. 只有需要时才重置
        return;
      }
      const nextSegments = await listSegments(authorId, documentId, chapterId);
      setSegments(nextSegments);
      // 3. 核心修改：如果是由于删除操作触发的同步，我们不希望历史记录被抹除
      if (shouldResetHistory) {
        resetSegmentHistory(chapters, nextSegments);
      }
    },
    [resetSegmentHistory]
  );

  const fetchSkillsOutputs = useCallback(async (jobId: string): Promise<SkillOutputs> => {
    const outputs = await listOutputs(jobId);
    const types = new Set(outputs.map((item) => item.type));

    async function fetchJson(type: string): Promise<any | null> {
      if (!types.has(type)) return null;
      try {
        const output = await getOutput(jobId, type);
        return output.content;
      } catch {
        return null;
      }
    }

    const mainSkillJson = await fetchJson("main_skill_json");
    const subSkillJson = await fetchJson("sub_skill_json");
    const mainSkillsMdJson = (await fetchJson("main_skills_md_json")) || [];
    const subSkillsMdJson = (await fetchJson("sub_skills_md_json")) || [];

    return {
      mainSkillJson: mainSkillJson && typeof mainSkillJson === "object" ? mainSkillJson : null,
      subSkillJson: subSkillJson && typeof subSkillJson === "object" ? subSkillJson : null,
      mainSkillsMdJson: Array.isArray(mainSkillsMdJson) ? mainSkillsMdJson : [],
      subSkillsMdJson: Array.isArray(subSkillsMdJson) ? subSkillsMdJson : [],
    };
  }, []);

  const loadLatestSkills = useCallback(
    async (authorId: string) => {
      const result = await listAuthorJobs({
        authorId,
        jobType: "author_skills",
        status: "success",
        limit: 1,
      });
      const latest = result.items[0] || null;
      setMethodologyRunningJob(latest);
      if (!latest || !latest.outputsReady) {
        setMethodologyOutputs(null);
        return;
      }
      const outputs = await fetchSkillsOutputs(latest.jobId);
      setMethodologyOutputs(outputs);
    },
    [fetchSkillsOutputs]
  );

  const ensureAnalysisHistory = useCallback(
    async (authorId: string, force = false) => {
      if (!force && analysisHistoryByAuthor[authorId]) return;
      setAnalysisLoadingByAuthor((prev) => ({ ...prev, [authorId]: true }));
      try {
        const result = await listAuthorJobs({
          authorId,
          jobType: "author_answer",
          limit: 50,
        });
        setAnalysisHistoryByAuthor((prev) => ({ ...prev, [authorId]: result.items }));
      } finally {
        setAnalysisLoadingByAuthor((prev) => ({ ...prev, [authorId]: false }));
      }
    },
    [analysisHistoryByAuthor]
  );

  const loadAnswerByJobId = useCallback(async (jobId: string) => {
    const output = await getOutput(jobId, "answer_json");
    const answer = parseAnswerJson(output.content);
    setAnswersByJob((prev) => ({ ...prev, [jobId]: answer }));
  }, []);

  useEffect(() => {
    refreshAuthors().catch(handleError);
  }, [refreshAuthors, handleError]);

  useEffect(() => {
    if (activeTab !== "archive") return;
    authors.forEach((author) => {
      ensureDocumentsLoaded(author.authorId).catch(handleError);
    });
  }, [activeTab, authors, ensureDocumentsLoaded, handleError]);

  useEffect(() => {
    if (!selectedSegmentAuthorId) return;
    ensureDocumentsLoaded(selectedSegmentAuthorId)
      .then(() => {
        const docs = documentsByAuthor[selectedSegmentAuthorId] || [];
        if (!docs.length) {
          setSelectedSegmentDocumentId(null);
          setSelectedSegmentChapterId(null);
          setSegments([]);
          resetSegmentHistory([], []);
          return;
        }
        const hasCurrentSelection =
          !!selectedSegmentDocumentId &&
          docs.some((item) => item.documentId === selectedSegmentDocumentId);
        if (!hasCurrentSelection) {
          setSelectedSegmentDocumentId(docs[0].documentId);
          setSelectedSegmentChapterId(null);
        }
      })
      .catch(handleError);
  }, [
    selectedSegmentAuthorId,
    selectedSegmentDocumentId,
    ensureDocumentsLoaded,
    documentsByAuthor,
    handleError,
    resetSegmentHistory,
  ]);

  useEffect(() => {
    if (!selectedSegmentAuthorId || !selectedSegmentDocumentId) return;
    syncSegmentView(selectedSegmentAuthorId, selectedSegmentDocumentId, selectedSegmentChapterId).catch(handleError);
  }, [selectedSegmentAuthorId, selectedSegmentDocumentId]); // intentionally exclude chapter to avoid loop

  useEffect(() => {
    if (activeTab !== "methodology" || !selectedMethodologyAuthorId) return;
    loadLatestSkills(selectedMethodologyAuthorId).catch(handleError);
  }, [activeTab, selectedMethodologyAuthorId, loadLatestSkills, handleError]);

  useEffect(() => {
    if (activeTab !== "answer" || !selectedAnalysisAuthorId) return;
    ensureAnalysisHistory(selectedAnalysisAuthorId).catch(handleError);
  }, [activeTab, selectedAnalysisAuthorId, ensureAnalysisHistory, handleError]);

  const handleCreateAuthor = async (payload: {
    authorName: string;
    school?: string;
    avatarFile?: File;
  }) => {
    try {
      setCreatingAuthor(true);
      const created = await createAuthor({
        authorName: payload.authorName,
        school: payload.school,
      });
      if (payload.avatarFile) {
        await uploadAuthorAvatar({
          authorId: created.authorId,
          file: payload.avatarFile,
        });
      }
      await refreshAuthors();
      setCreateAuthorOpen(false);
    } catch (error) {
      handleError(error);
      await refreshAuthors().catch(() => undefined);
    } finally {
      setCreatingAuthor(false);
    }
  };

  const handleUploadAvatar = async (authorId: string, file: File) => {
    try {
      setAvatarUploadingAuthorId(authorId);
      await uploadAuthorAvatar({ authorId, file });
      await refreshAuthors();
    } catch (error) {
      handleError(error);
    } finally {
      setAvatarUploadingAuthorId(null);
    }
  };

  const handleRenameAuthor = async (authorId: string, authorName: string) => {
    try {
      setRenameSavingAuthorId(authorId);
      await updateAuthor(authorId, { authorName });
      await refreshAuthors();
    } catch (error) {
      handleError(error);
      throw error;
    } finally {
      setRenameSavingAuthorId(null);
    }
  };

  const handleUpdateAuthorSchool = async (authorId: string, newSchool: string) => {
    // 1. 更新内存状态，让 UI 实时变动
    setAuthors(prev => prev.map(a => 
      a.authorId === authorId ? { ...a, school: newSchool } : a
    ));

    // 2. 如果你需要持久化（刷新不丢失），请更新缓存或调用后端 API
    const cache = JSON.parse(localStorage.getItem('author_data_cache') || '{}');
    if(!cache[authorId]) cache[authorId] = {};
    cache[authorId].school = newSchool;
    localStorage.setItem('author_data_cache', JSON.stringify(cache));
  };



  const handleUploadDocument = async (payload: { authorId: string; bookTitle: string; file: File }) => {
    try {
      setUploadingDocument(true);
      const created = await uploadDocumentFile(payload);
      const finalJob = await pollJob(created.reloadJobId);
      if (finalJob.status !== "success") {
        throw new Error(finalJob.errorMessage || `reload failed: ${finalJob.status}`);
      }
      await ensureDocumentsLoaded(payload.authorId, true);
    } catch (error) {
      handleError(error);
    } finally {
      setUploadingDocument(false);
    }
  };

  const handleReloadDocument = async (authorId: string, documentId: string) => {
    try {
      setReloadingDocumentId(documentId);
      const created = await reloadDocument(authorId, documentId);
      const finalJob = await pollJob(created.reloadJobId);
      if (finalJob.status !== "success") {
        throw new Error(finalJob.errorMessage || `reload failed: ${finalJob.status}`);
      }
      await ensureDocumentsLoaded(authorId, true);
      if (selectedSegmentDocumentId === documentId && selectedSegmentAuthorId === authorId) {
        await syncSegmentView(authorId, documentId, selectedSegmentChapterId);
      }
    } catch (error) {
      handleError(error);
    } finally {
      setReloadingDocumentId(null);
    }
  };

  const handleDeleteAuthor = async (authorId: string) => {
    try {
      setDeletingAuthorId(authorId);
      await deleteAuthor(authorId);
      setDocumentsByAuthor((prev) => {
        const next = { ...prev };
        delete next[authorId];
        return next;
      });
      await refreshAuthors();
    } catch (error) {
      handleError(error);
    } finally {
      setDeletingAuthorId(null);
    }
  };

  const handleDeleteChapter = async (authorId: string, documentId: string, chapterId: string) => {
    const currentChapters = chaptersByDocument[documentId] || [];
    const nextChapters = currentChapters.filter((item) => item.chapterId !== chapterId);
    const nextChapterId =
      selectedSegmentChapterId === chapterId ? nextChapters[0]?.chapterId || null : selectedSegmentChapterId;
    const nextSegments = selectedSegmentChapterId === chapterId ? [] : segments;

    setChaptersByDocument((prev) => ({ ...prev, [documentId]: nextChapters }));
    setSelectedSegmentChapterId(nextChapterId);
    setSegments(nextSegments);
    pushSegmentHistory(nextChapters, nextSegments);

    try {
      await deleteChapter(authorId, documentId, chapterId);
    } catch (error) {
      handleError(error);
    } finally {
      await syncSegmentView(authorId, documentId, nextChapterId, false).catch(handleError);
    }
  };

  const handleDeleteSegment = async (segmentId: string) => {
    if (!selectedSegmentAuthorId || !selectedSegmentDocumentId) return;
    const currentChapters = chaptersByDocument[selectedSegmentDocumentId] || [];
    const nextSegments = segments.filter((item) => item.segmentId !== segmentId);
    setSegments(nextSegments);
    pushSegmentHistory(currentChapters, nextSegments);

    try {
      await deleteSegment(selectedSegmentAuthorId, selectedSegmentDocumentId, segmentId);
    } catch (error) {
      handleError(error);
    } finally {
      await syncSegmentView(
        selectedSegmentAuthorId,
        selectedSegmentDocumentId,
        selectedSegmentChapterId,
        false
      ).catch(handleError);
    }
  };

  const handleUndoSegment = () => {
    if (segmentHistoryIndex <= 0 || !selectedSegmentDocumentId) return;
    const index = segmentHistoryIndex - 1;
    const snapshot = segmentHistory[index];
    setSegmentHistoryIndex(index);
    setChaptersByDocument((prev) => ({ ...prev, [selectedSegmentDocumentId]: snapshot.chapters }));
    setSegments(snapshot.segments);
  };

  const handleRedoSegment = () => {
    if (segmentHistoryIndex >= segmentHistory.length - 1 || !selectedSegmentDocumentId) return;
    const index = segmentHistoryIndex + 1;
    const snapshot = segmentHistory[index];
    setSegmentHistoryIndex(index);
    setChaptersByDocument((prev) => ({ ...prev, [selectedSegmentDocumentId]: snapshot.chapters }));
    setSegments(snapshot.segments);
  };

  const handleRefreshSegments = async () => {
    if (!selectedSegmentAuthorId || !selectedSegmentDocumentId) return;
    await syncSegmentView(selectedSegmentAuthorId, selectedSegmentDocumentId, selectedSegmentChapterId).catch(
      handleError
    );
  };

  const handleGenerateSkills = async () => {
    if (!selectedMethodologyAuthorId) return;
    try {
      setMethodologyGenerating(true);
      const created = await createSkillsJob(
        selectedMethodologyAuthorId,
        toModelConfigOrUndefined(runtimeSettings.skillsModel)
      );
      const finalJob = await pollJob(created.jobId, {
        onProgress(job) {
          setMethodologyRunningJob(job);
        },
      });
      setMethodologyRunningJob(finalJob);
      if (finalJob.status !== "success") {
        throw new Error(finalJob.errorMessage || `skills failed: ${finalJob.status}`);
      }
      await loadLatestSkills(selectedMethodologyAuthorId);
    } catch (error) {
      handleError(error);
    } finally {
      setMethodologyGenerating(false);
    }
  };

  const handleRefreshMethodology = async () => {
    if (!selectedMethodologyAuthorId) return;
    await loadLatestSkills(selectedMethodologyAuthorId).catch(handleError);
  };

  const handleDeleteMethodologySection = async (sectionId: string) => {
    if (!selectedMethodologyAuthorId || !sectionId.trim()) return;
    try {
      setMethodologyDeletingSectionId(sectionId);
      await deleteMainSkillSection(selectedMethodologyAuthorId, sectionId);
      await loadLatestSkills(selectedMethodologyAuthorId);
    } catch (error) {
      handleError(error);
    } finally {
      setMethodologyDeletingSectionId(null);
    }
  };

  const handleSelectAnswerJob = async (jobId: string) => {
    setSelectedAnswerJobId(jobId);
    if (answersByJob[jobId]) return;
    await loadAnswerByJobId(jobId).catch(handleError);
  };

  const handleGenerateAnswer = async () => {
    if (!selectedAnalysisAuthorId || !answerQuery.trim()) return;
    try {
      setAnswerCreating(true);
      const created = await createAnswerJob({
        authorId: selectedAnalysisAuthorId,
        query: answerQuery.trim(),
        modelConfig: toModelConfigOrUndefined(runtimeSettings.answerModel),
      });
      const finalJob = await pollJob(created.jobId, {
        onProgress(job) {
          setAnalysisRunningJob(job);
          setAnalysisHistoryByAuthor((prev) => {
            const existing = prev[job.authorId] || [];
            const index = existing.findIndex((item) => item.jobId === job.jobId);
            const next =
              index >= 0
                ? existing.map((item, i) => (i === index ? job : item))
                : [job, ...existing];
            return { ...prev, [job.authorId]: next };
          });
        },
      });
      setAnalysisRunningJob(finalJob);
      if (finalJob.status !== "success") {
        throw new Error(finalJob.errorMessage || `answer failed: ${finalJob.status}`);
      }
      await ensureAnalysisHistory(selectedAnalysisAuthorId, true);
      setSelectedAnswerJobId(created.jobId);
      await loadAnswerByJobId(created.jobId);
    } catch (error) {
      handleError(error);
    } finally {
      setAnswerCreating(false);
      setAnalysisRunningJob(null);
    }
  };

  const handleDeleteAnswerHistory = async (jobId: string) => {
    const resolvedAuthorId =
      Object.entries(analysisHistoryByAuthor).find(([, jobs]) =>
        jobs.some((job) => job.jobId === jobId)
      )?.[0] || selectedAnalysisAuthorId;
    if (!resolvedAuthorId) return;

    try {
      setDeletingAnswerJobId(jobId);
      await deleteAuthorAnswerJob(resolvedAuthorId, jobId);
      setAnswersByJob((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
      if (selectedAnswerJobId === jobId) {
        setSelectedAnswerJobId(null);
      }
      await ensureAnalysisHistory(resolvedAuthorId, true);
    } catch (error) {
      handleError(error);
    } finally {
      setDeletingAnswerJobId(null);
    }
  };

  return (
    <div className="min-h-screen bg-background text-on-background font-body flex flex-col">
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} onSettingsOpen={() => setSettingsOpen(true)} />

      <AnimatePresence mode="wait">
        {activeTab === "landing" && <LandingPage onStart={() => setActiveTab("archive")} />}
      </AnimatePresence>

      <main className="pt-20 flex-grow flex flex-col">
        {globalError && (
          <div className="mx-8 mt-4 mb-2 px-4 py-3 bg-error/10 border border-error/30 rounded-sm text-sm text-error">
            {globalError}
          </div>
        )}

        {activeTab === "archive" ? (
          <div className="max-w-7xl mx-auto px-12 py-12 w-full">
            <header className="flex flex-col md:flex-row justify-between items-start md:items-end mb-16 gap-6">
              <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
                <h1 className="font-headline text-5xl font-medium tracking-tight text-on-background mb-4">
                  Textual Archive
                </h1>
                <p className="font-body text-secondary text-lg max-w-xl leading-relaxed">
                  Manage authors and documents from backend data.
                </p>
              </motion.div>
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setCreateAuthorOpen(true)}
                className="bg-primary text-on-primary px-8 py-3 rounded-sm font-label text-sm font-semibold tracking-wide hover:bg-primary-dim transition-all shadow-md active:translate-y-px"
              >
                Create New Author
              </motion.button>
            </header>

            <div className="grid grid-cols-12 gap-8">
              <Sidebar
                authors={authors}
                selectedAuthorId={selectedArchiveAuthorId}
                uploading={uploadingDocument}
                onAuthorChange={(authorId) => {
                  setSelectedArchiveAuthorId(authorId);
                  ensureDocumentsLoaded(authorId).catch(handleError);
                }}
                onUpload={handleUploadDocument}
              />

              <section className="col-span-12 lg:col-span-8 space-y-12">
                {authors.map((author) => (
                  <AuthorSection
                    key={author.authorId}
                    author={author}
                    documents={documentsByAuthor[author.authorId] || []}
                    reloadingDocumentId={reloadingDocumentId}
                    deletingAuthor={deletingAuthorId === author.authorId}
                    avatarUploading={avatarUploadingAuthorId === author.authorId}
                    renameSaving={renameSavingAuthorId === author.authorId}
                    onReloadDocument={(documentId) => handleReloadDocument(author.authorId, documentId)}
                    onDeleteAuthor={() => handleDeleteAuthor(author.authorId)}
                    onUploadAvatar={(file) => handleUploadAvatar(author.authorId, file)}
                    onRenameAuthor={(authorName) => handleRenameAuthor(author.authorId, authorName)}
                    onUpdateSchool={(newSchool) => handleUpdateAuthorSchool(author.authorId, newSchool)} // 确保学派能存
                  />
                ))}
              </section>
            </div>
          </div>
        ) : activeTab === "analysis" ? (
          <div className="flex flex-1 overflow-hidden">
            <SegmentSidebar
              authors={authors}
              documentsByAuthor={documentsByAuthor}
              chaptersByDocument={chaptersByDocument}
              selectedAuthorId={selectedSegmentAuthorId}
              selectedDocumentId={selectedSegmentDocumentId}
              selectedChapterId={selectedSegmentChapterId}
              onExpandAuthor={(authorId) => ensureDocumentsLoaded(authorId).catch(handleError)}
              onSelectAuthor={(authorId) => {
                setSelectedSegmentAuthorId(authorId);
                setSelectedSegmentDocumentId(null);
                setSelectedSegmentChapterId(null);
                setSegments([]);
                resetSegmentHistory([], []);
              }}
              onSelectDocument={async (authorId, documentId) => {
                setSelectedSegmentAuthorId(authorId);
                setSelectedSegmentDocumentId(documentId);
                await syncSegmentView(authorId, documentId, null).catch(handleError);
              }}
              onSelectChapter={async (authorId, documentId, chapterId) => {
                setSelectedSegmentAuthorId(authorId);
                setSelectedSegmentDocumentId(documentId);
                setSelectedSegmentChapterId(chapterId);
                try {
                  const chapterSegments = await listSegments(authorId, documentId, chapterId);
                  setSegments(chapterSegments);
                  resetSegmentHistory(chaptersByDocument[documentId] || [], chapterSegments);
                } catch (error) {
                  handleError(error);
                }
              }}
              onDeleteChapter={handleDeleteChapter}
            />
            <SegmentView
              selectedAuthorName={currentSegmentAuthor?.authorName || ""}
              selectedBookTitle={currentSegmentDocument?.bookTitle || ""}
              selectedChapterTitle={currentSegmentChapter?.chapterTitle || ""}
              segments={segments}
              onDeleteSegment={handleDeleteSegment}
              onUndo={handleUndoSegment}
              onRedo={handleRedoSegment}
              onRefresh={handleRefreshSegments}
              historyIndex={segmentHistoryIndex}
              historyLength={segmentHistory.length}
            />
          </div>
        ) : activeTab === "methodology" ? (
          <div className="flex flex-1 overflow-hidden">
            <MethodologySidebar
              authors={authors}
              selectedAuthorId={selectedMethodologyAuthorId}
              onSelect={(authorId) => setSelectedMethodologyAuthorId(authorId)}
            />
            <MethodologyView
              selectedAuthor={selectedMethodologyAuthor}
              runningJob={
                methodologyRunningJob?.authorId === selectedMethodologyAuthorId
                  ? methodologyRunningJob
                  : null
              }
              outputs={methodologyOutputs}
              generating={methodologyGenerating}
              deletingSectionId={methodologyDeletingSectionId}
              onGenerate={handleGenerateSkills}
              onRefresh={handleRefreshMethodology}
              onDeleteMainSkill={handleDeleteMethodologySection}
            />
          </div>
        ) : activeTab === "answer" ? (
          <div className="flex flex-1 overflow-hidden">
            <AnalysisSidebar
              authors={authors}
              selectedAuthorId={selectedAnalysisAuthorId}
              selectedJobId={selectedAnswerJobId}
              deletingJobId={deletingAnswerJobId}
              historyByAuthor={analysisHistoryByAuthor}
              loadingByAuthor={analysisLoadingByAuthor}
              onExpandAuthor={(authorId) => ensureAnalysisHistory(authorId).catch(handleError)}
              onSelectAuthor={(authorId) => setSelectedAnalysisAuthorId(authorId)}
              onSelectJob={(jobId) => handleSelectAnswerJob(jobId).catch(handleError)}
              onDeleteJob={handleDeleteAnswerHistory}
              onNewAnalysis={() => setSelectedAnswerJobId(null)}
            />
            <AnalysisView
              authors={authors}
              selectedAuthorId={selectedAnalysisAuthorId}
              query={answerQuery}
              creating={answerCreating}
              selectedAnswer={selectedAnswer}
              selectedJob={selectedAnswerJob}
              runningJob={
                analysisRunningJob?.authorId === selectedAnalysisAuthorId
                  ? analysisRunningJob
                  : null
              }
              onSelectAuthor={(authorId) => {
                setSelectedAnalysisAuthorId(authorId);
                ensureAnalysisHistory(authorId).catch(handleError);
              }}
              onQueryChange={setAnswerQuery}
              onGenerate={handleGenerateAnswer}
            />
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-secondary italic">View coming soon...</div>
        )}
      </main>

      <footer className="py-12 px-12 border-t border-outline-variant/10 bg-surface-container-low/30 mt-auto">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-[10px] font-label uppercase tracking-[0.2em] text-outline-variant">
          <span>The Lexicon Project - Archive Node Alpha</span>
          <span>Est. 2024 - Academic Modern Collective</span>
        </div>
      </footer>

      <AnimatePresence>
        {isCreateAuthorOpen && (
          <CreateAuthorModal
            isOpen={isCreateAuthorOpen}
            submitting={creatingAuthor}
            onClose={() => setCreateAuthorOpen(false)}
            onCreate={handleCreateAuthor}
          />
        )}
        {isSettingsOpen && (
          <SettingsModal
            isOpen={isSettingsOpen}
            value={runtimeSettings}
            onClose={() => setSettingsOpen(false)}
            onSave={(next) => setRuntimeSettings(next)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
