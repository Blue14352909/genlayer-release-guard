/** Normalize thrown values (SDK/RPC errors) into a readable message. */

export interface NormalizedError {
  title: string;
  detail: string;
}

function rawMessage(error: unknown): string {
  if (!error) return "";
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  if (typeof error === "object") {
    const withMessage = error as { message?: unknown; shortMessage?: unknown };
    if (typeof withMessage.shortMessage === "string") {
      return withMessage.shortMessage;
    }
    if (typeof withMessage.message === "string") return withMessage.message;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

export function normalizeError(error: unknown): NormalizedError {
  const message = rawMessage(error).trim();
  const lower = message.toLowerCase();

  if (!message) {
    return {
      title: "Something went wrong",
      detail: "The request failed without returning a message. Please try again.",
    };
  }

  if (lower.includes("verification not found")) {
    return {
      title: "No such verification",
      detail:
        "No verification with that id exists on the deployed ReleaseGuard contract. Check the id and try again.",
    };
  }

  if (
    lower.includes("failed to fetch") ||
    lower.includes("fetch failed") ||
    lower.includes("network") ||
    lower.includes("econn") ||
    lower.includes("timeout") ||
    lower.includes("cors") ||
    lower.includes("blocked")
  ) {
    return {
      title: "Could not reach the network",
      detail:
        "The read against GenLayer Studionet did not complete. This is a public RPC read — wait a moment, then retry.",
    };
  }

  if (lower.includes("execution failed") || lower.includes("gen_call")) {
    return {
      title: "The contract rejected the read",
      detail:
        "The contract raised an error for this id. Confirm the verification id and that it exists on the deployed contract.",
    };
  }

  return {
    title: "Request failed",
    detail: message.length > 600 ? `${message.slice(0, 600)}…` : message,
  };
}
