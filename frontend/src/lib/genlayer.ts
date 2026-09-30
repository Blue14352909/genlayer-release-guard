import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import {
  executionResultNumberToName,
  transactionsStatusNumberToName,
  TransactionStatus,
  type GenLayerTransaction,
} from "genlayer-js/types";
import { CONTRACT_ADDRESS } from "./config";
import type { CheckResult, Verification } from "./types";
import type { EIP1193Provider } from "./wallet";

/**
 * Thin wrapper over the GenLayerJS SDK (genlayer-js 1.1.8 — the stable `latest`
 * release, which is the only published version whose `gen_call` encoding works
 * against the live Studionet deployment).
 *
 * Write flow used by this app:
 *   1. `simulateWriteContract` — a pre-flight dry run (`sim_call` on Studio).
 *      It validates the call without changing state and returns the value the
 *      contract method *would* return (e.g. the next verification id).
 *   2. `writeContract` — the SDK estimates gas via `estimateTransactionGas`
 *      before submitting the EVM transaction to the consensus contract, then
 *      routes signing through the injected browser wallet.
 *   3. `getTransaction` / `waitForTransactionReceipt` — wait for the decision
 *      before reading state again.
 */

type SdkClient = ReturnType<typeof createClient>;
/** The hash type the SDK expects for transaction lookups. */
type SdkTxHash = Parameters<SdkClient["getTransaction"]>[0]["hash"];
type SdkClientConfig = NonNullable<Parameters<typeof createClient>[0]>;
type SdkProvider = NonNullable<SdkClientConfig["provider"]>;

export function createReadClient(): SdkClient {
  return createClient({ chain: studionet });
}

export function createWalletClient(
  address: string,
  provider: EIP1193Provider,
): SdkClient {
  return createClient({
    chain: studionet,
    account: address as `0x${string}`,
    provider: provider as unknown as SdkProvider,
  });
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

/* ------------------------------- reads ---------------------------------- */

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

/* ------------------------------ writes ---------------------------------- */

export interface CreateVerificationInput {
  projectName: string;
  version: string;
  evidenceUrl: string;
  policyText: string;
}

/**
 * Pre-flight: simulate create_verification. Returns the contract's predicted
 * return value (the verification id) without submitting anything. The id is
 * only a prediction — it is confirmed against chain state after the real
 * transaction is decided.
 */
export async function preflightCreateVerification(
  input: CreateVerificationInput,
): Promise<string> {
  const client = createReadClient();
  const raw = await client.simulateWriteContract({
    address: CONTRACT_ADDRESS,
    functionName: "create_verification",
    args: [
      input.projectName,
      input.version,
      input.evidenceUrl,
      input.policyText,
    ],
  });
  return asString(raw);
}

export async function submitCreateVerification(
  client: SdkClient,
  input: CreateVerificationInput,
): Promise<string> {
  const hash = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "create_verification",
    args: [
      input.projectName,
      input.version,
      input.evidenceUrl,
      input.policyText,
    ],
    value: BigInt(0),
  });
  return asString(hash);
}

export async function submitRunVerification(
  client: SdkClient,
  verificationId: string,
): Promise<string> {
  const hash = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "run_verification",
    args: [verificationId],
    value: BigInt(0),
  });
  return asString(hash);
}

/* ---------------------------- lifecycle --------------------------------- */

const STATUS_NUMBER_TO_NAME = transactionsStatusNumberToName as unknown as Record<
  number,
  string
>;
const EXEC_NUMBER_TO_NAME = executionResultNumberToName as unknown as Record<
  number,
  string
>;

export function txStatusName(tx: {
  statusName?: unknown;
  status?: unknown;
}): string {
  if (typeof tx.statusName === "string") return tx.statusName;
  if (typeof tx.status === "string") return tx.status;
  if (typeof tx.status === "number") {
    return STATUS_NUMBER_TO_NAME[tx.status] ?? `STATUS_${tx.status}`;
  }
  return "UNKNOWN";
}

export function txExecName(tx: {
  txExecutionResultName?: unknown;
  txExecutionResult?: unknown;
}): string {
  if (typeof tx.txExecutionResultName === "string") {
    return tx.txExecutionResultName;
  }
  if (typeof tx.txExecutionResult === "number") {
    return EXEC_NUMBER_TO_NAME[tx.txExecutionResult] ?? "UNKNOWN";
  }
  if (typeof tx.txExecutionResult === "string") return tx.txExecutionResult;
  return "UNKNOWN";
}

/** Statuses that mean the transaction reached a decision point. */
const DECIDED_STATUSES: readonly string[] = [
  TransactionStatus.ACCEPTED,
  TransactionStatus.UNDETERMINED,
  TransactionStatus.FINALIZED,
  TransactionStatus.CANCELED,
  TransactionStatus.VALIDATORS_TIMEOUT,
  TransactionStatus.LEADER_TIMEOUT,
];

export interface DecisionResult {
  hash: string;
  statusName: string;
  execName: string;
  transaction: GenLayerTransaction;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Poll the node until the transaction reaches a decided status. Reports each
 * new status name so the UI can show the lifecycle without inventing progress.
 */
export async function waitForDecision(
  hash: string,
  onUpdate?: (statusName: string) => void,
  { intervalMs = 4000, timeoutMs = 10 * 60 * 1000 } = {},
): Promise<DecisionResult> {
  const client = createReadClient();
  const startedAt = Date.now();
  let lastReported = "";

  while (Date.now() - startedAt < timeoutMs) {
    const tx = await client.getTransaction({ hash: hash as SdkTxHash });
    const statusName = txStatusName(tx);
    if (statusName !== lastReported) {
      lastReported = statusName;
      onUpdate?.(statusName);
    }
    if (DECIDED_STATUSES.includes(statusName)) {
      return {
        hash,
        statusName,
        execName: txExecName(tx),
        transaction: tx,
      };
    }
    await sleep(intervalMs);
  }

  throw new Error(
    `Timed out after ${Math.round(
      timeoutMs / 1000,
    )}s waiting for transaction ${hash} to be decided.`,
  );
}

/** Read the final verification id back from chain after a create transaction. */
export function expectedMatches(
  verification: Verification | null,
  input: CreateVerificationInput,
): boolean {
  if (!verification) return false;
  return (
    verification.project_name === input.projectName &&
    verification.version === input.version &&
    verification.evidence_url === input.evidenceUrl
  );
}
