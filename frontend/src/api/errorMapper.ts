import { ApiClientError } from "./client";

export interface UiError {
  title: string;
  message: string;
  retryable: boolean;
}

export function mapApiErrorToUi(error: unknown): UiError {
  if (!(error instanceof ApiClientError)) {
    return {
      title: "未知错误",
      message: error instanceof Error ? error.message : "请求失败，请稍后重试。",
      retryable: true,
    };
  }

  switch (error.code) {
    case "UNAUTHORIZED":
      return {
        title: "鉴权失败",
        message: "请检查 X-API-Key 或后端鉴权配置。",
        retryable: false,
      };
    case "NOT_FOUND":
      return {
        title: "资源不存在",
        message: error.message || "目标资源不存在，可能已删除。",
        retryable: false,
      };
    case "TASK_CONFLICT":
      return {
        title: "任务状态冲突",
        message: error.message || "当前任务状态不支持该操作。",
        retryable: true,
      };
    case "INVALID_ARGUMENT":
      return {
        title: "请求参数错误",
        message: error.message || "请检查输入参数后重试。",
        retryable: false,
      };
    default:
      return {
        title: "服务异常",
        message: error.message || "后端内部错误，请稍后重试。",
        retryable: true,
      };
  }
}
