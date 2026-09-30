import Link from "next/link";
import { ExternalLink } from "@/components/ExternalLink";
import {
  CONTRACT_ADDRESS,
  EVIDENCE_LINKS,
  EXAMPLE,
  NETWORK_NAME,
  SUPPORTED_POLICIES,
  addressUrl,
} from "@/lib/config";

const STEPS = [
  {
    title: "Submit release evidence",
    body: "Provide the project name, version, an HTTPS evidence URL, and the checks you want run. Nothing runs until you sign the transaction.",
  },
  {
    title: "GenLayer evaluates the evidence",
    body: "Independent validators render the page, extract stable facts, derive a categorical verdict, and reach consensus on source, license, and vulnerability evidence.",
  },
  {
    title: "Receive a deterministic outcome",
    body: "The final verdict is composed by deterministic, fail-closed code — VERIFIED, REJECTED, or INCONCLUSIVE. No LLM decides the final verdict.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4">
      {/* Hero */}
      <section className="pt-16 pb-14 sm:pt-24">
        <span className="chip" style={{ color: "var(--color-accent)" }}>
          GenLayer Studionet · fail-closed attestation
        </span>
        <h1 className="mt-5 max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl">
          Verify software releases before you trust them.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted">
          ReleaseGuard independently evaluates public release evidence through
          GenLayer consensus. Each check fetches the evidence page, extracts
          stable facts, derives a categorical verdict, and requires independent
          validators to agree. The final outcome is composed by deterministic
          code — not by a model.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/new" className="btn btn-primary">
            Create Verification
          </Link>
          <Link
            href={`/inspect?id=${EXAMPLE.verificationId}`}
            className="btn btn-secondary"
          >
            Inspect Existing Result
          </Link>
        </div>
        <p className="mt-4 text-xs text-muted">
          Submitting a verification requires a browser wallet and test GEN on{" "}
          {NETWORK_NAME}. Network fees apply to the on-chain transaction.
        </p>
      </section>

      {/* How it works */}
      <section aria-labelledby="how" className="py-12">
        <h2 id="how" className="text-2xl font-bold tracking-tight">
          How it works
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <div key={step.title} className="card card-pad">
              <span
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold"
                style={{
                  color: "var(--color-accent)",
                  backgroundColor: "rgba(34, 211, 238, 0.12)",
                }}
              >
                {index + 1}
              </span>
              <h3 className="mt-3 text-base font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-muted">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Supported checks */}
      <section aria-labelledby="checks" className="py-12">
        <h2 id="checks" className="text-2xl font-bold tracking-tight">
          Supported checks
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          A comma-separated policy selects which checks run. Only these three
          are wired into the orchestrator; any other name fails closed.
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {SUPPORTED_POLICIES.map((policy) => (
            <div key={policy.name} className="card card-pad">
              <p className="mono" style={{ color: "var(--color-accent-2)" }}>
                {policy.name}
              </p>
              <h3 className="mt-2 text-base font-semibold">{policy.label}</h3>
              <p className="mt-2 text-sm text-muted">{policy.help}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Fail-closed */}
      <section aria-labelledby="failclosed" className="py-12">
        <div
          className="card card-pad"
          style={{ borderColor: "rgba(251, 191, 36, 0.4)" }}
        >
          <h2
            id="failclosed"
            className="text-2xl font-bold tracking-tight"
            style={{ color: "var(--color-inconclusive)" }}
          >
            Fail-closed by design
          </h2>
          <p className="mt-3 max-w-3xl text-lg">
            Missing, malformed, unavailable, ambiguous, or non-consensus
            evidence cannot produce VERIFIED.
          </p>
          <div className="mt-5 grid gap-3 text-sm text-muted sm:grid-cols-3">
            <p>
              <strong style={{ color: "var(--color-verified)" }}>
                VERIFIED
              </strong>{" "}
              — every requested check explicitly passed.
            </p>
            <p>
              <strong style={{ color: "var(--color-rejected)" }}>
                REJECTED
              </strong>{" "}
              — at least one requested check failed.
            </p>
            <p>
              <strong style={{ color: "var(--color-inconclusive)" }}>
                INCONCLUSIVE
              </strong>{" "}
              — evidence or consensus could not establish a confident result.
            </p>
          </div>
          <p className="mt-5 text-xs text-muted">
            The composition rule is enforced in contract code:{" "}
            <code className="mono">
              all PASS → VERIFIED · any FAIL → REJECTED · otherwise INCONCLUSIVE
            </code>
            . A fetch failure or consensus failure is recorded as
            INSUFFICIENT_EVIDENCE, never as PASS.
          </p>
        </div>
      </section>

      {/* Evidence */}
      <section id="evidence" aria-labelledby="evidence-heading" className="py-12">
        <h2 id="evidence-heading" className="text-2xl font-bold tracking-tight">
          Evidence
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Verify the deployment and a real VERIFIED execution yourself. These
          links point at the deployed contract on {NETWORK_NAME}.
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="card card-pad">
            <p className="text-xs tracking-wide text-muted uppercase">
              Source code
            </p>
            <p className="mt-2">
              <ExternalLink href={EVIDENCE_LINKS.github}>
                github.com/Blue14352909/genlayer-release-guard
              </ExternalLink>
            </p>
          </div>
          <div className="card card-pad">
            <p className="text-xs tracking-wide text-muted uppercase">
              Studio deployment
            </p>
            <p className="mt-2">
              <ExternalLink href={EVIDENCE_LINKS.deployTx}>
                Deployment transaction
              </ExternalLink>
            </p>
          </div>
          <div className="card card-pad">
            <p className="text-xs tracking-wide text-muted uppercase">
              Verified execution
            </p>
            <p className="mt-2">
              <ExternalLink href={EVIDENCE_LINKS.verifiedTx}>
                VERIFIED execution transaction
              </ExternalLink>
            </p>
          </div>
        </div>
        <div className="card card-pad mt-4">
          <p className="text-xs tracking-wide text-muted uppercase">
            Deployed contract
          </p>
          <p className="mono mt-2 break-all">
            <ExternalLink href={addressUrl(CONTRACT_ADDRESS)}>
              {CONTRACT_ADDRESS}
            </ExternalLink>
          </p>
        </div>
      </section>
    </div>
  );
}
