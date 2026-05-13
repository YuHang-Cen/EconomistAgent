export type ApiErrorCode =
  | "UNAUTHORIZED"
  | "NOT_FOUND"
  | "TASK_CONFLICT"
  | "INVALID_ARGUMENT"
  | "INTERNAL_ERROR";

export type ApiEnvelope<T> =
  | {
      success: true;
      data: T;
      error: null;
      requestId: string;
      timestamp: string;
    }
  | {
      success: false;
      data: null;
      error: {
        code: ApiErrorCode | string;
        message: string;
        details?: unknown;
      };
      requestId: string;
      timestamp: string;
    };

export interface ModelConfig {
  provider?: string;
  modelName?: string;
  apiBase?: string;
  apiKey?: string;
}

export interface AuthorVM {
  authorId: string;
  authorName: string;
  school: string | null;
  language: "english" | "chinese";
  avatarUrl: string | null;
  manuscriptsCount: number;
}

export interface DocumentVM {
  documentId: string;
  authorId: string;
  bookTitle: string;
  pdfUri: string;
  status: "processing" | "active" | "failed" | string;
}

export interface ChapterVM {
  chapterId: string;
  documentId: string;
  chapterTitle: string;
  orderIndex: number;
}

export interface SegmentVM {
  segmentId: string;
  documentId: string;
  chapterId: string;
  chunkId: string;
  content: string;
  orderIndex: number;
}

export interface JobVM {
  jobId: string;
  authorId: string;
  documentId: string | null;
  jobType: "document_reload" | "author_skills" | "author_answer" | string;
  status: "queued" | "running" | "success" | "failed" | "canceled" | string;
  currentStage: string | null;
  progress: number;
  query: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
  finishedAt: string | null;
  retryable: boolean;
  outputsReady: boolean;
}

export interface JobListVM {
  items: JobVM[];
  nextCursor: string | null;
}

export interface OutputTypeVM {
  type: string;
}

export interface OutputContentVM {
  type: string;
  content: unknown;
}

export interface AnswerVM {
  query: string;
  generatedAt: string | null;
  modelName: string | null;
  apiBase: string | null;
  selectedSkillIndices: number[];
  selectedSectionIds: string[];
  selectedSkillIndex: number | null;
  selectedSectionId: string | null;
  selectedMainSkillNames: string[];
  selectedMainSkillName: string | null;
  selectedSubSkillNames: string[];
  selectionMode: "llm" | "fallback_rule" | string;
  selectionWarning: string | null;
  answer: {
    title: string;
    topic: string;
    summary: string;
    markdown: string;
  };
}
