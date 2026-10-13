"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "next/navigation";
import { CheckResultsList } from "@/components/CheckResultsList";
import { ErrorCard } from "@/components/ErrorCard";
import { ExternalLink } from "@/components/ExternalLink";
import { VerdictBadge } from "@/components/VerdictBadge";
import { CONTRACT_ADDRESS, EXAMPLE, NETWORK_NAME } from "@/lib/config";
import { normalizeError } from "@/lib/errors";
import { isHttpsUrl, sanitizeText } from "@/lib/format";
import { readCheckResults, readVerdict, readVerification } from "@/lib/genlayer";
import { describePolicies } from "@/lib/policy";
import type { CheckResult, Verification } from "@/lib/types";

type Phase = "idle" | "loading";

interface Failure {
  title: string;
  detail: string;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{children}</td>
    </tr>
  );
}

export default function InspectPage() {
  // `useSearchParams` needs a Suspense boundary so the route can still be
  // prerendered; the inspector renders on the client.
  return (
    <Suspense fallback={<InspectFallback />}>
      <InspectView />
    </Suspense>
  );
}

function InspectFallback() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <div className="panel panel-pad">
        <p className="text-[0.9375rem] text-muted">Loading inspector…</p>
      </div>
    </div>
  );
}

function InspectView() {
  const searchParams = useSearchParams();
  const queryId = searchParams.get("id") ?? "";

  const [idInput, setIdInput] = useState(queryId);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [verdict, setVerdict] = useState<string | null>(null);
  const [results, setResults] = useState<CheckResult[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [failure, setFailure] = useState<Failure | null>(null);
  const [loaded, setLoaded] = useState(false);

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
      // Primary read: the stored record already contains the verdict and the
      // per-check results, so one call is enough to render the page. Keeping
      // the critical path to a single request avoids bursting the public RPC.
      const record = await readVerification(id);
      setVerification(record);
      setVerdict(record.verdict || null);
      setResults(record.results);
      setLoaded(true);

      // Enrichment reads are best-effort. If the public RPC rejects one (for
      // example a transient CORS or rate limit), the record still renders from
      // the primary read instead of collapsing into an error state.
      const [verdictOutcome, checksOutcome] = await Promise.allSettled([
        readVerdict(id),
        readCheckResults(id),
      ]);
      if (verdictOutcome.status === "fulfilled" && verdictOutcome.value) {
        setVerdict(verdictOutcome.value);
      }
      if (
        checksOutcome.status === "fulfilled" &&
        checksOutcome.value.length > 0
      ) {
        setResults(checksOutcome.value);
      }
    } catch (err) {
      setVerification(null);
      setVerdict(null);
      setResults([]);
      setFailure(normalizeError(err));
    } finally {
      setPhase("idle");
    }
  }, []);

  // Deep links such as /inspect?id=v-1 prefill the input above and auto-load.
  // The load is scheduled as a task rather than run inline so no state is
  // committed synchronously from an effect body.
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

  const status = verification?.status ?? "";
  const isPending = status === "PENDING" || status === "RUNNING";
  const busy = phase === "loading";

  const evidenceUrl = verification?.evidence_url ?? "";
  const evidenceIsLink = isHttpsUrl(evidenceUrl);
  const policies = describePolicies(verification?.policy_text ?? "");
  const isExample = idInput.trim() === EXAMPLE.verificationId;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <header className="mb-8">
        <p className="eyebrow">Verify a result</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">
          Inspect a stored verification.
        </h1>
        <p className="lede mt-3 max-w-2xl">
          Enter a verification id to read it directly from the deployed
          contract. Every value shown is a real contract read — the Console
          stores nothing and never connects a wallet.
        </p>
      </header>

      <form
        className="panel panel-pad"
        onSubmit={(e) => {
          e.preventDefault();
          void load(idInput);
        }}
      >
        <label className="label" htmlFor="vid">
          Verification id
        </label>
        <div className="flex flex-wrap gap-3">
          <input
            id="vid"
            className="input flex-1 min-w-[12rem]"
            value={idInput}
            onChange={(e) => setIdInput(e.target.value)}
            placeholder="v-1"
            autoComplete="off"
            spellCheck={false}
            disabled={busy}
          />
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Reading…" : "Load verification"}
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
            Load example (v-1)
          </button>
        </div>
        <p className="mt-3 text-[0.9375rem] text-muted">
          Example: <span className="mono">{EXAMPLE.verificationId}</span> — the
          verified <span className="mono">requests 2.31.0</span> record.
        </p>
      </form>

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

      {!verification && !failure && !loaded ? (
        <p className="mt-6 text-[0.9375rem] text-muted">
          No result loaded yet. Enter a verification id or load the verified
          example.
        </p>
      ) : null}

      {verification ? (
        <div className="mt-6 grid gap-6">
          <div className="panel panel-pad">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="mono text-muted">Final verdict</p>
                <div className="mt-2">
                  <VerdictBadge
                    verdict={
                      isPending ? status : (verdict ?? verification.verdict)
                    }
                    size="lg"
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {isExample ? (
                  <span className="chip">Verified example</span>
                ) : null}
                <span className="chip">{sanitizeText(verification.id, 40)}</span>
              </div>
            </div>

            {isPending ? (
              <p className="mt-5 text-[0.9375rem] text-muted">
                This record has not produced a verdict yet. Running a
                verification requires a transaction, which this read-only
                console does not submit — use GenLayer Studio to execute it,
                then reload this page.
              </p>
            ) : null}
          </div>

          <div className="panel panel-pad">
            <h2 className="text-lg font-semibold">Record</h2>
            <table className="data-table mt-2">
              <tbody>
                <Row label="Project">
                  <span className="strong">
                    {sanitizeText(verification.project_name, 200) || "—"}
                  </span>
                </Row>
                <Row label="Version">
                  <span className="mono">
                    {sanitizeText(verification.version, 80) || "—"}
                  </span>
                </Row>
                <Row label="Evidence URL">
                  {evidenceIsLink ? (
                    <ExternalLink href={evidenceUrl} className="link break-all">
                      {sanitizeText(evidenceUrl, 300)}
                    </ExternalLink>
                  ) : (
                    <span className="break-all">
                      {sanitizeText(evidenceUrl, 300) || "—"}
                    </span>
                  )}
                </Row>
                <Row label="Policy">
                  <span className="mono">
                    {policies.length > 0
                      ? policies
                          .map((p) =>
                            p.supported
                              ? p.name
                              : `${p.name} (unsupported)`,
                          )
                          .join(", ")
                      : "—"}
                  </span>
                </Row>
                <Row label="Status">
                  <span className="mono">
                    {sanitizeText(verification.status, 40) || "—"}
                  </span>
                </Row>
                <Row label="Reason code">
                  <span className="mono">
                    {sanitizeText(verification.reason_code, 80) || "—"}
                  </span>
                </Row>
                <Row label="Failed checks">
                  <span className="mono">
                    {sanitizeText(verification.failed_checks, 200) || "—"}
                  </span>
                </Row>
              </tbody>
            </table>
          </div>

          <div className="panel panel-pad">
            <h2 className="text-lg font-semibold">Check results</h2>
            <div className="mt-4">
              <CheckResultsList results={results} />
            </div>
          </div>
        </div>
      ) : null}

      <p className="mt-8 text-[0.9375rem] text-muted">
        Contract <span className="mono break-all">{CONTRACT_ADDRESS}</span> on{" "}
        {NETWORK_NAME}. Reads use{" "}
        <span className="mono">get_verification</span>,{" "}
        <span className="mono">get_verdict</span>, and{" "}
        <span className="mono">get_check_results</span>.
      </p>
    </div>
  );
}
