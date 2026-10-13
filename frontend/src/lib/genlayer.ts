import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { CONTRACT_ADDRESS } from "./config";
import type { CheckResult, Verification } from "./types";

/**
 * Read-only client for the deployed ReleaseGuard contract.
 *
 * This module exposes the public read path only:
 *   get_verification(id)  -> dict
 *   get_verdict(id)       -> str
 *   get_check_results(id) -> list
 *
 * There is intentionally no write path here. ReleaseGuard Console is a
 * read-only workspace: it never asks for a wallet, a signature, or a
 * transaction. Reads are free and require no account.
 *
 * The app pins genlayer-js 1.1.8 (the stable `latest` release). It is the only
 * published version whose `gen_call` encoding reads this Studionet deployment;
 * the 2.0.0-rc line fails `readContract` against the same contract.
 */

function createReadClient() {
  return createClient({ chain: studionet });
}

function asString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return fallback;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

export function normalizeCheckResults(raw: unknown): CheckResult[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => {
    const r = asRecord(item);
    return {
      check_name: asString(r.check_name, "unknown"),
      status: asString(r.status, "UNKNOWN"),
      evidence: asString(r.evidence),
      reason: asString(r.reason),
    };
  });
}

export function normalizeVerification(raw: unknown): Verification {
  const r = asRecord(raw);
  return {
    id: asString(r.id),
    project_name: asString(r.project_name),
    version: asString(r.version),
    evidence_url: asString(r.evidence_url),
    policy_text: asString(r.policy_text),
    status: asString(r.status, "UNKNOWN"),
    verdict: asString(r.verdict),
    reason_code: asString(r.reason_code),
    failed_checks: asString(r.failed_checks),
    results: normalizeCheckResults(r.results),
  };
}

export async function readVerification(id: string): Promise<Verification> {
  const client = createReadClient();
  const raw = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName: "get_verification",
    args: [id],
  });
  return normalizeVerification(raw);
}

export async function tryReadVerification(
  id: string,
): Promise<Verification | null> {
  try {
    return await readVerification(id);
  } catch {
    return null;
  }
}

export async function readVerdict(id: string): Promise<string> {
  const client = createReadClient();
  const raw = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName: "get_verdict",
    args: [id],
  });
  return asString(raw, "UNKNOWN");
}

export async function readCheckResults(id: string): Promise<CheckResult[]> {
  const client = createReadClient();
  const raw = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName: "get_check_results",
    args: [id],
  });
  return normalizeCheckResults(raw);
}
