"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ErrorCard } from "@/components/ErrorCard";
import { ExternalLink } from "@/components/ExternalLink";
import { PolicySelector } from "@/components/PolicySelector";
import { TxLifecycle, type LifecycleStep } from "@/components/TxLifecycle";
import {
  CHAIN_ID_HEX,
  CONTRACT_ADDRESS,
  EXAMPLE,
  NETWORK_NAME,
  txUrl,
  type PolicyName,
} from "@/lib/config";
import { normalizeError } from "@/lib/errors";
import { isHttpsUrl, sanitizeText, truncateMiddle } from "@/lib/format";
import {
  createWalletClient,
  expectedMatches,
  preflightCreateVerification,
  submitCreateVerification,
  tryReadVerification,
  waitForDecision,
} from "@/lib/genlayer";
import { useWallet } from "@/lib/wallet-context";

type Phase = "idle" | "preflight" | "submitting" | "waiting" | "done" | "error";

interface Failure {
  title: string;
  detail: string;
}

export default function NewVerificationPage() {
  const wallet = useWallet();

  const [projectName, setProjectName] = useState("");
  const [version, setVersion] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [policies, setPolicies] = useState<PolicyName[]>(["source"]);

  const [phase, setPhase] = useState<Phase>("idle");
  const [failure, setFailure] = useState<Failure | null>(null);
  const [validation, setValidation] = useState<string | null>(null);

  const [predictedId, setPredictedId] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [decisionStatus, setDecisionStatus] = useState<string | null>(null);
  const [execName, setExecName] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [manualId, setManualId] = useState("");

  const policyText = policies.join(",");
  const busy = phase === "preflight" || phase === "submitting" || phase === "waiting";

  function togglePolicy(policy: PolicyName) {
    setPolicies((prev) =>
      prev.includes(policy)
        ? prev.filter((p) => p !== policy)
        : [...prev, policy],
    );
  }

  function fillExample() {
    setProjectName(EXAMPLE.projectName);
    setVersion(EXAMPLE.version);
    setEvidenceUrl(EXAMPLE.evidenceUrl);
    setPolicies([...EXAMPLE.policies]);
    setValidation(null);
    setFailure(null);
  }

  const steps = useMemo<LifecycleStep[]>(() => {
    const validated: LifecycleStep["state"] =
      phase === "idle" ? "idle" : "done";
    const preflight: LifecycleStep["state"] = predictedId
      ? "done"
      : phase === "preflight"
        ? "active"
        : phase === "error"
          ? "error"
          : "idle";
    const submitted: LifecycleStep["state"] = txHash
      ? "done"
      : phase === "submitting"
        ? "active"
        : "idle";
    const decided: LifecycleStep["state"] =
      decisionStatus && ["ACCEPTED", "FINALIZED"].includes(decisionStatus)
        ? "done"
        : phase === "waiting"
          ? "active"
          : decisionStatus
            ? "error"
            : "idle";
    return [
      {
        key: "validated",
        label: "Inputs validated",
        detail: policyText ? `policy_text = ${policyText}` : undefined,
        state: validated,
      },
      {
        key: "preflight",
        label: "Pre-flight simulation (no state change)",
        detail: predictedId ? `contract would return ${predictedId}` : undefined,
        state: preflight,
      },
      {
        key: "submitted",
        label: "Signed in wallet and submitted",
        detail: txHash ?? undefined,
        state: submitted,
      },
      {
        key: "decided",
        label: "Decision reached",
        detail: decisionStatus ?? undefined,
        state: decided,
      },
    ];
  }, [phase, predictedId, txHash, decisionStatus, policyText]);

  async function handleCreate() {
    setValidation(null);
    setFailure(null);

    const project = projectName.trim();
    const ver = version.trim();
    const url = evidenceUrl.trim();

    if (!project) return setValidation("Project name is required.");
    if (!ver) return setValidation("Version is required.");
    if (!url) return setValidation("Evidence URL is required.");
    if (!isHttpsUrl(url)) {
      return setValidation("Evidence URL must be a valid HTTPS URL.");
    }
    if (policies.length === 0) {
      return setValidation(
        "Select at least one policy check. An empty policy is valid on-chain but always fails closed to INCONCLUSIVE.",
      );
    }
    if (!wallet.available || !wallet.address) {
      setFailure({
        title: "Wallet not connected",
        detail:
          "Connect an EIP-1193 browser wallet (for example MetaMask) in the header before creating a verification.",
      });
      return;
    }
    if (!wallet.isCorrectNetwork) {
      setFailure({
        title: "Wrong network",
        detail: `Your wallet is not on ${NETWORK_NAME} (chain id ${CHAIN_ID_HEX}). Use the switch control in the header, then try again.`,
      });
      return;
    }

    const input = {
      projectName: project,
      version: ver,
      evidenceUrl: url,
      policyText,
    };

    try {
      setPhase("preflight");
      setPredictedId(null);
      setTxHash(null);
      setDecisionStatus(null);
      setExecName(null);
      setCreatedId(null);

      // 1. Pre-flight: simulate the call. This validates the parameters and
      //    returns the value the contract would return (the next id) without
      //    changing any state.
      const predicted = await preflightCreateVerification(input);
      setPredictedId(predicted || null);

      // 2. Submit through the connected wallet. The SDK estimates gas before
      //    building the transaction, then asks the wallet to sign.
      setPhase("submitting");
      const client = createWalletClient(wallet.address, wallet.provider!);
      const hash = await submitCreateVerification(client, input);
      if (!hash) {
        throw new Error("The wallet did not return a transaction hash.");
      }
      setTxHash(hash);

      // 3. Wait for the decision before reading state again.
      setPhase("waiting");
      const decision = await waitForDecision(hash, (status) =>
        setDecisionStatus(status),
      );
      setDecisionStatus(decision.statusName);
      setExecName(decision.execName);

      if (decision.execName === "FINISHED_WITH_ERROR") {
        throw new Error(
          "The transaction was decided but the contract execution failed. No verification was created.",
        );
      }

      // 4. Confirm the predicted id against real chain state. The prediction
      //    is never shown as a fact until it reads back correctly.
      const idToConfirm = predicted || "";
      const confirmed = idToConfirm
        ? await tryReadVerification(idToConfirm)
        : null;
      if (idToConfirm && expectedMatches(confirmed, input)) {
        setCreatedId(idToConfirm);
      }
      setPhase("done");
    } catch (err) {
      setFailure(normalizeError(err));
      setPhase("error");
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">
          New verification
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Create a release verification on the deployed contract. Inputs are
          validated first, the call is simulated as a pre-flight, and the
          outcome is only reported after the on-chain transaction is decided.
        </p>
      </header>

      <div className="card card-pad">
        <div className="grid gap-5">
          <div>
            <label className="label" htmlFor="project">
              Project name <span aria-hidden="true">*</span>
            </label>
            <input
              id="project"
              className="input"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="requests"
              autoComplete="off"
              disabled={busy}
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="version">
              Version <span aria-hidden="true">*</span>
            </label>
            <input
              id="version"
              className="input"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="2.31.0"
              autoComplete="off"
              disabled={busy}
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="url">
              Evidence URL (HTTPS) <span aria-hidden="true">*</span>
            </label>
            <input
              id="url"
              className="input"
              value={evidenceUrl}
              onChange={(e) => setEvidenceUrl(e.target.value)}
              placeholder="https://pypi.org/project/requests/2.31.0/"
              inputMode="url"
              autoComplete="off"
              disabled={busy}
              aria-describedby="url-help"
              required
            />
            <p id="url-help" className="mt-1 text-xs text-muted">
              The URL must contain evidence for every selected policy. HTTPS
              format is checked here, but that does <strong>not</strong> prove
              the source is trustworthy.
            </p>
          </div>

          <PolicySelector
            selected={policies}
            onToggle={togglePolicy}
            disabled={busy}
          />

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void handleCreate()}
              disabled={busy}
            >
              {busy ? "Working…" : "Create Verification"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={fillExample}
              disabled={busy}
            >
              Try the verified example
            </button>
          </div>

          <p className="text-xs text-muted">
            Calling the contract requires test GEN on {NETWORK_NAME} and may
            incur Studionet transaction fees. Your wallet signs the
            transaction; this app never holds a key.
          </p>
        </div>
      </div>

      {validation ? (
        <div className="mt-4">
          <ErrorCard title="Check the form" detail={validation} />
        </div>
      ) : null}

      {failure ? (
        <div className="mt-4">
          <ErrorCard title={failure.title} detail={failure.detail} />
        </div>
      ) : null}

      {phase !== "idle" ? (
        <div className="card card-pad mt-6">
          <h2 className="text-lg font-semibold">Transaction lifecycle</h2>
          <div className="mt-4">
            <TxLifecycle steps={steps} />
          </div>

          {execName && execName !== "UNKNOWN" ? (
            <p className="mt-4 text-xs text-muted">
              Execution result: <span className="mono">{execName}</span>
            </p>
          ) : null}
          {decisionStatus && execName === "UNKNOWN" ? (
            <p className="mt-4 text-xs text-muted">
              The node did not report an execution result for this transaction.
              Confirm the result by reading the verification below.
            </p>
          ) : null}

          {txHash ? (
            <p className="mt-4 text-sm">
              Transaction:{" "}
              <ExternalLink href={txUrl(txHash)} className="link">
                <span className="mono">{truncateMiddle(txHash, 10, 8)}</span>
              </ExternalLink>
            </p>
          ) : null}
        </div>
      ) : null}

      {createdId ? (
        <div
          className="card card-pad mt-6"
          style={{ borderColor: "rgba(163, 230, 53, 0.45)" }}
        >
          <h2 className="text-lg font-semibold">
            Verification created: <span className="mono">{createdId}</span>
          </h2>
          <p className="mt-2 text-sm text-muted">
            Confirmed by reading the contract back. It is currently pending —
            run it to execute the checks.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              href={`/inspect?id=${encodeURIComponent(createdId)}`}
              className="btn btn-primary"
            >
              Run Verification
            </Link>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setPhase("idle");
                setPredictedId(null);
                setTxHash(null);
                setDecisionStatus(null);
                setExecName(null);
                setCreatedId(null);
              }}
            >
              Create another
            </button>
          </div>
        </div>
      ) : null}

      {phase === "done" && !createdId ? (
        <div className="card card-pad mt-6">
          <h2 className="text-lg font-semibold">
            Transaction decided — verification id not auto-confirmed
          </h2>
          <p className="mt-2 text-sm text-muted">
            The contract write was submitted
            {predictedId ? (
              <>
                {" "}
                (pre-flight predicted <span className="mono">{predictedId}</span>)
              </>
            ) : null}
            , but this app could not confirm the new id by reading it back — for
            example if another transaction was created first. No id is invented
            here. Open the confirmed transaction result above, copy the
            verification id it returned, and paste it below.
          </p>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <div className="min-w-[14rem] flex-1">
              <label className="label" htmlFor="manual-id">
                Paste the verification id
              </label>
              <input
                id="manual-id"
                className="input"
                value={manualId}
                onChange={(e) => setManualId(e.target.value)}
                placeholder="v-2"
                autoComplete="off"
              />
            </div>
            <Link
              href={`/inspect?id=${encodeURIComponent(manualId.trim())}`}
              className="btn btn-secondary"
              aria-disabled={manualId.trim() ? undefined : true}
              style={
                manualId.trim() ? undefined : { pointerEvents: "none", opacity: 0.5 }
              }
            >
              Inspect id
            </Link>
          </div>
        </div>
      ) : null}

      <p className="mt-8 text-xs text-muted">
        Contract <span className="mono">{sanitizeText(CONTRACT_ADDRESS, 64)}</span>{" "}
        on {NETWORK_NAME}.
      </p>
    </div>
  );
}
