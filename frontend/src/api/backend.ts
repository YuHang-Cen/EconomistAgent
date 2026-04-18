import { apiRequest } from "./client";
import type {
  AuthorVM,
  ChapterVM,
  DocumentVM,
  JobListVM,
  JobVM,
  ModelConfig,
  OutputContentVM,
  OutputTypeVM,
  SegmentVM,
} from "./types";

export function listAuthors(): Promise<AuthorVM[]> {
  return apiRequest<AuthorVM[]>("/authors");
}

export function createAuthor(input: {
  authorName: string;
  school?: string;
  avatarUrl?: string;
}): Promise<AuthorVM> {
  return apiRequest<AuthorVM>("/authors", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteAuthor(authorId: string): Promise<{ deleted: true }> {
  return apiRequest<{ deleted: true }>(`/authors/${authorId}`, {
    method: "DELETE",
  });
}

export function listDocuments(authorId: string): Promise<DocumentVM[]> {
  return apiRequest<DocumentVM[]>(`/authors/${authorId}/documents`);
}

export function uploadDocument(input: {
  authorId: string;
  bookTitle: string;
  pdfUri: string;
}): Promise<{ documentId: string; reloadJobId: string }> {
  return apiRequest<{ documentId: string; reloadJobId: string }>(
    `/authors/${input.authorId}/documents`,
    {
      method: "POST",
      body: JSON.stringify({
        bookTitle: input.bookTitle,
        pdfUri: input.pdfUri,
      }),
    }
  );
}

export function reloadDocument(
  authorId: string,
  documentId: string
): Promise<{ reloadJobId: string }> {
  return apiRequest<{ reloadJobId: string }>(
    `/authors/${authorId}/documents/${documentId}/reload`,
    {
      method: "POST",
    }
  );
}

export function listChapters(authorId: string, documentId: string): Promise<ChapterVM[]> {
  return apiRequest<ChapterVM[]>(`/authors/${authorId}/documents/${documentId}/chapters`);
}

export function listSegments(
  authorId: string,
  documentId: string,
  chapterId: string
): Promise<SegmentVM[]> {
  return apiRequest<SegmentVM[]>(
    `/authors/${authorId}/documents/${documentId}/chapters/${chapterId}/segments`
  );
}

export function deleteChapter(
  authorId: string,
  documentId: string,
  chapterId: string
): Promise<{ deleted: true }> {
  return apiRequest<{ deleted: true }>(
    `/authors/${authorId}/documents/${documentId}/chapters/${chapterId}`,
    {
      method: "DELETE",
    }
  );
}

export function deleteSegment(
  authorId: string,
  documentId: string,
  segmentId: string
): Promise<{ deleted: true }> {
  return apiRequest<{ deleted: true }>(
    `/authors/${authorId}/documents/${documentId}/segments/${segmentId}`,
    {
      method: "DELETE",
    }
  );
}

export function createSkillsJob(
  authorId: string,
  modelConfig?: ModelConfig
): Promise<{ jobId: string }> {
  const body = modelConfig ? JSON.stringify({ modelConfig }) : undefined;
  return apiRequest<{ jobId: string }>(`/authors/${authorId}/jobs/skills`, {
    method: "POST",
    body,
  });
}

export function createAnswerJob(input: {
  authorId: string;
  query: string;
  modelConfig?: ModelConfig;
}): Promise<{ jobId: string }> {
  return apiRequest<{ jobId: string }>(`/authors/${input.authorId}/jobs/answer`, {
    method: "POST",
    body: JSON.stringify({
      query: input.query,
      modelConfig: input.modelConfig,
    }),
  });
}

export function listAuthorJobs(input: {
  authorId: string;
  jobType?: string;
  status?: string;
  limit?: number;
  cursor?: string;
}): Promise<JobListVM> {
  const params = new URLSearchParams();
  if (input.jobType) params.set("jobType", input.jobType);
  if (input.status) params.set("status", input.status);
  if (typeof input.limit === "number") params.set("limit", String(input.limit));
  if (input.cursor) params.set("cursor", input.cursor);
  const query = params.toString();
  return apiRequest<JobListVM>(
    `/authors/${input.authorId}/jobs${query ? `?${query}` : ""}`
  );
}

export function getJob(jobId: string): Promise<JobVM> {
  return apiRequest<JobVM>(`/jobs/${jobId}`);
}

export function retryJob(jobId: string): Promise<JobVM> {
  return apiRequest<JobVM>(`/jobs/${jobId}/retry`, { method: "POST" });
}

export function cancelJob(jobId: string): Promise<JobVM> {
  return apiRequest<JobVM>(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export function listOutputs(jobId: string): Promise<OutputTypeVM[]> {
  return apiRequest<OutputTypeVM[]>(`/jobs/${jobId}/outputs`);
}

export function getOutput(jobId: string, outputType: string): Promise<OutputContentVM> {
  return apiRequest<OutputContentVM>(`/jobs/${jobId}/outputs/${outputType}`);
}
