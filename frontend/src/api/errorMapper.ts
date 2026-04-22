import { ApiClientError } from "./client";

export interface UiError {
  title: string;
  message: string;
  retryable: boolean;
}

export function mapApiErrorToUi(error: unknown): UiError {
  if (!(error instanceof ApiClientError)) {
    return {
      title: "Unknown Error",
      message: error instanceof Error ? error.message : "Request failed. Please retry.",
      retryable: true,
    };
  }

  switch (error.code) {
    case "UNAUTHORIZED":
      return {
        title: "Unauthorized",
        message: "Check X-API-Key and backend API_KEY configuration.",
        retryable: false,
      };
    case "NOT_FOUND":
      return {
        title: "Not Found",
        message: error.message || "The requested resource does not exist.",
        retryable: false,
      };
    case "TASK_CONFLICT":
      return {
        title: "Task Conflict",
        message: error.message || "Current task state does not allow this operation.",
        retryable: true,
      };
    case "INVALID_ARGUMENT":
      if ((error.message || "").includes("missing model api key")) {
        return {
          title: "Model API Key Missing",
          message:
            "Set DEEPSEEK_API_KEY in backend/.env or provide modelConfig.apiKey before creating skills/answer jobs.",
          retryable: false,
        };
      }
      return {
        title: "Invalid Request",
        message: error.message || "Check request parameters and retry.",
        retryable: false,
      };
    default:
      return {
        title: "Server Error",
        message: error.message || "Backend internal error. Please retry later.",
        retryable: true,
      };
  }
}
