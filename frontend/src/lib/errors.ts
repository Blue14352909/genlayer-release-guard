/** Normalize thrown values (SDK/viem/wallet errors) into a readable message. */

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

  if (lower.includes("user rejected") || lower.includes("user denied")) {
    return {
      title: "Request rejected in wallet",
      detail: "You declined the signature request. Nothing was submitted.",
    };
  }

  if (lower.includes("no injected") || lower.includes("no ethereum")) {
    return {
      title: "No wallet detected",
      detail:
        "Install an EIP-1193 browser wallet (for example MetaMask), then reload this page.",
    };
  }

  if (lower.includes("wallet is on chain")) {
    return {
      title: "Wrong network",
      detail:
        "Your wallet is connected to a different chain. Switch to GenLayer Studionet and try again.",
    };
  }

  if (lower.includes("verification not found")) {
    return {
      title: "Verification not found",
      detail:
        "No verification with that ID exists on the deployed ReleaseGuard contract.",
    };
  }

  if (lower.includes("not pending")) {
    return {
      title: "Already executed",
      detail:
        "This verification is no longer pending. Reload it to see the stored result.",
    };
  }

  if (lower.includes("execution failed")) {
    return {
      title: "Contract rejected the call",
      detail:
        "The contract raised an error. Check the verification ID and the requested parameters.",
    };
  }

  return {
    title: "Request failed",
    detail: message.length > 600 ? `${message.slice(0, 600)}…` : message,
  };
}
