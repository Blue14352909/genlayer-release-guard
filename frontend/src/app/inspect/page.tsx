"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "next/navigation";
import { CheckStatusBadge } from "@/components/CheckStatusBadge";
import { ErrorCard } from "@/components/ErrorCard";
import { ExternalLink } from "@/components/ExternalLink";
import { TxLifecycle, type LifecycleStep } from "@/components/TxLifecycle";
import { VerdictBadge } from "@/components/VerdictBadge";
import {
  CHAIN_ID_HEX,
  CONTRACT_ADDRESS,
  EXAMPLE,
  NETWORK_NAME,
  txUrl,
} from "@/lib/config";
import { normalizeError } from "@/lib/errors";
import { isHttpsUrl, sanitizeText, truncateMiddle } from "@/lib/format";
import {
  createWalletClient,
  readCheckResults,
  readVerdict,
  readVerification,
  submitRunVerification,
  waitForDecision,
} from "@/lib/genlayer";
import type { CheckResult, Verification } from "@/lib/types";
import { useWallet } from "@/lib/wallet-context";

type Phase = "idle" | "loading" | "submitting" | "waiting";

interface Failure {
  title: string;
  detail: string;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs tracking-wide text-muted uppercase">{label}</dt>
      <dd className="mt-1 text-sm break-words">{children}</dd>
    </div>
  );
}

function ResultList({ results }: { results: CheckResult[] }) {
  if (results.length === 0) {
    return (
      <p className="text-sm text-muted">
        The contract returned no individual check results for this verification.
      </p>
    );
  }
  return (
    <ul className="grid gap-3">
      {results.map((result, index) => (
        <li key={`${result.check_name}-${index}`} className="card card-pad">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="mono" style={{ color: "var(--color-accent-2)" }}>
              {sanitizeText(result.check_name, 40)}
            </span>
            <CheckStatusBadge status={result.status} />
          </div>
          {result.evidence ? (
            <p className="mt-3 text-sm">
              <span className="text-muted">Evidence: </span>
              {sanitizeText(result.evidence, 400)}
            </p>
          ) : null}
          {result.reason ? (
            <p className="mt-1 text-sm">
              <span className="text-muted">Reason: </span>
              {sanitizeText(result.reason, 600)}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export default function InspectPage() {
  // `useSearchParams` requires a Suspense boundary so the route can still be
  // prerendered; the inspector itself then renders on the client.
  return (
    <Suspense fallback={<InspectFallback />}>
      <InspectView />
    </Suspense>
  );
}

function InspectFallback() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="card card-pad">
        <p className="text-sm text-muted">Loading inspector…</p>
      </div>
    </div>
  );
}

function InspectView() {
  const wallet = useWallet();
  const searchParams = useSearchParams();
  const queryId = searchParams.get("id") ?? "";

  const [idInput, setIdInput] = useState(queryId);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [verdict, setVerdict] = useState<string | null>(null);
  const [results, setResults] = useState<CheckResult[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [failure, setFailure] = useState<Failure | null>(null);

  const [runHash, setRunHash] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);

  const load = useCallback(async (rawId: string) => {
    const id = rawId.trim();
    setFailure(null);
    if (!id) {
      setFailure({
        title: "Verification id required",
        detail: "Enter a verification id such as v-1.",
      });
      return;
    }
    setPhase("loading");
    try {
      const [record, currentVerdict, checks] = await Promise.all([
        readVerification(id),
        readVerdict(id),
        readCheckResults(id),
      ]);
      setVerification(record);
      setVerdict(currentVerdict);
      setResults(checks.length > 0 ? checks : record.results);
    } catch (err) {
      setVerification(null);
      setVerdict(null);
      setResults([]);
      setFailure(normalizeError(err));
    } finally {
      setPhase("idle");
    }
  }, []);

  // Deep links such as /inspect?id=v-2 prefill the input above and auto-load.
  // The load is scheduled as a task rather than run inline so no state is
  // committed synchronously from an effect body. Cancelling on cleanup keeps
  // this correct under StrictMode's mount/unmount/remount cycle.
  useEffect(() => {
    if (!queryId) return;
    let cancelled = false;
    const task = window.setTimeout(() => {
      if (cancelled) return;
      void load(queryId);
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(task);
    };
  }, [queryId, load]);

  async function handleRun() {
    if (!verification) return;
    setFailure(null);
    if (!wallet.available || !wallet.address) {
      setFailure({
        title: "Wallet not connected",
        detail: "Connect a browser wallet before running the verification.",
      });
      return;
    }
    if (!wallet.isCorrectNetwork) {
      setFailure({
        title: "Wrong network",
        detail: `Switch your wallet to ${NETWORK_NAME} (chain id ${CHAIN_ID_HEX}) first.`,
      });
      return;
    }

    const id = verification.id;
    try {
      setRunHash(null);
      setRunStatus(null);
      setPhase("submitting");
      const client = createWalletClient(wallet.address, wallet.provider!);
      const hash = await submitRunVerification(client, id);
      if (!hash) {
        throw new Error("The wallet did not return a transaction hash.");
      }
      setRunHash(hash);

      setPhase("waiting");
      const decision = await waitForDecision(hash, setRunStatus);
      setRunStatus(decision.statusName);
      if (decision.execName === "FINISHED_WITH_ERROR") {
        throw new Error(
          "The run transaction was decided but execution failed. The stored result was not updated.",
        );
      }

      // Refresh only after the decision is available.
      await load(id);
      setPhase("idle");
    } catch (err) {
      setFailure(normalizeError(err));
      setPhase("idle");
    }
  }

  const isPending =
    verification?.status === "PENDING" || verification?.status === "RUNNING";
  const busy = phase === "loading" || phase === "submitting" || phase === "waiting";

  const runSteps: LifecycleStep[] = [
    { key: "prep", label: "Transaction prepared", state: runHash ? "done" : phase === "submitting" ? "active" : "idle" },
    { key: "submitted", label: "Signed in wallet and submitted", detail: runHash ?? undefined, state: runHash ? "done" : "idle" },
    {
      key: "decided",
      label: "Decision reached",
      detail: runStatus ?? undefined,
      state:
        runStatus && ["ACCEPTED", "FINALIZED"].includes(runStatus)
          ? "done"
          : phase === "waiting"
            ? "active"
            : "idle",
    },
  ];

  const evidenceUrl = verification?.evidence_url ?? "";
  const evidenceIsLink = isHttpsUrl(evidenceUrl);

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">Inspect result</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Read a stored verification directly from the deployed contract. All
          values below come from real contract reads.
        </p>
      </header>

      <div className="card card-pad">
        <label className="label" htmlFor="vid">
          Verification id
        </label>
        <div className="flex flex-wrap gap-3">
          <input
            id="vid"
            className="input flex-1 min-w-[12rem]"
            value={idInput}
            onChange={(e) => setIdInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void load(idInput);
            }}
            placeholder="v-1"
            autoComplete="off"
            disabled={busy}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void load(idInput)}
            disabled={busy}
          >
            {phase === "loading" ? "Loading…" : "Load Verification"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setIdInput(EXAMPLE.verificationId);
              void load(EXAMPLE.verificationId);
            }}
            disabled={busy}
          >
            Load example ({EXAMPLE.verificationId})
          </button>
        </div>
      </div>

      {failure ? (
        <div className="mt-4">
          <ErrorCard
            title={failure.title}
            detail={failure.detail}
            action={
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => void load(idInput)}
                disabled={busy}
              >
                Retry
              </button>
            }
          />
        </div>
      ) : null}

      {verification ? (
        <div className="mt-6 grid gap-6">
          <div className="card card-pad">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs tracking-wide text-muted uppercase">
                  Final verdict
                </p>
                <div className="mt-2">
                  <VerdictBadge
                    verdict={
                      isPending
                        ? verification.status
                        : (verdict ?? verification.verdict)
                    }
                    size="lg"
                  />
                </div>
              </div>
              <span className="chip mono">{sanitizeText(verification.id, 40)}</span>
            </div>

            {isPending ? (
              <div className="mt-5">
                <p className="text-sm text-muted">
                  This verification has not been executed yet. Running it
                  executes the requested checks through GenLayer consensus.
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void handleRun()}
                    disabled={busy}
                  >
                    {busy ? "Working…" : "Run Verification"}
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="card card-pad">
            <h2 className="text-lg font-semibold">Record</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Project">{sanitizeText(verification.project_name, 200)}</Field>
              <Field label="Version">{sanitizeText(verification.version, 80)}</Field>
              <Field label="Policy text">
                <span className="mono">
                  {sanitizeText(verification.policy_text, 200) || "(empty)"}
                </span>
              </Field>
              <Field label="Request status">
                <span className="mono">{sanitizeText(verification.status, 40)}</span>
              </Field>
              <Field label="Reason code">
                <span className="mono">
                  {sanitizeText(verification.reason_code, 80) || "—"}
                </span>
              </Field>
              <Field label="Failed checks">
                <span className="mono">
                  {sanitizeText(verification.failed_checks, 200) || "—"}
                </span>
              </Field>
              <Field label="Evidence URL">
                {evidenceIsLink ? (
                  <ExternalLink href={evidenceUrl} className="link">
                    <span className="break-all">{sanitizeText(evidenceUrl, 300)}</span>
                  </ExternalLink>
                ) : (
                  <span className="break-all">
                    {sanitizeText(evidenceUrl, 300) || "—"}
                  </span>
                )}
              </Field>
            </dl>
          </div>

          <div className="card card-pad">
            <h2 className="text-lg font-semibold">Check results</h2>
            <div className="mt-4">
              <ResultList results={results} />
            </div>
          </div>

          {phase === "submitting" || phase === "waiting" || runHash ? (
            <div className="card card-pad">
              <h2 className="text-lg font-semibold">Run transaction</h2>
              <div className="mt-4">
                <TxLifecycle steps={runSteps} />
              </div>
              {runHash ? (
                <p className="mt-4 text-sm">
                  Transaction:{" "}
                  <ExternalLink href={txUrl(runHash)} className="link">
                    <span className="mono">{truncateMiddle(runHash, 10, 8)}</span>
                  </ExternalLink>
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <p className="mt-8 text-xs text-muted">
        Contract <span className="mono">{sanitizeText(CONTRACT_ADDRESS, 64)}</span>{" "}
        on {NETWORK_NAME}.
      </p>
    </div>
  );
}
