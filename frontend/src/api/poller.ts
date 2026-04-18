import { getJob } from "./backend";
import type { JobVM } from "./types";

export interface PollJobOptions {
  intervalMs?: number;
  timeoutMs?: number;
  onProgress?: (job: JobVM) => void;
}

const TERMINAL_STATUS = new Set(["success", "failed", "canceled"]);

export async function pollJob(
  jobId: string,
  options: PollJobOptions = {}
): Promise<JobVM> {
  const intervalMs = options.intervalMs ?? 2000;
  const timeoutMs = options.timeoutMs ?? 10 * 60 * 1000;
  const deadline = Date.now() + timeoutMs;

  while (true) {
    const job = await getJob(jobId);
    options.onProgress?.(job);
    if (TERMINAL_STATUS.has(job.status)) {
      return job;
    }
    if (Date.now() >= deadline) {
      return {
        ...job,
        status: "running",
        message: "The task is still being processed in the background."
      } as JobVM;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
