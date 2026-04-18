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
  const intervalMs = options.intervalMs ?? 1000;
  const timeoutMs = options.timeoutMs ?? 180000;
  const deadline = Date.now() + timeoutMs;

  while (true) {
    const job = await getJob(jobId);
    options.onProgress?.(job);
    if (TERMINAL_STATUS.has(job.status)) {
      return job;
    }
    if (Date.now() >= deadline) {
      throw new Error(`job polling timeout: ${jobId}`);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
