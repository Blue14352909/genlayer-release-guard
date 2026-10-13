import Link from "next/link";
import { Callout } from "@/components/Callout";
import { ExternalLink } from "@/components/ExternalLink";
import { VerdictBadge } from "@/components/VerdictBadge";
import { VerdictLegend } from "@/components/VerdictLegend";
import {
  CONTRACT_ADDRESS,
  EVIDENCE_LINKS,
  EXAMPLE,
  NETWORK_NAME,
  STUDIO_IMPORT_URL,
  SUPPORTED_POLICIES,
  addressUrl,
} from "@/lib/config";

const STEPS = [
  {
    title: "Claim",
    body: "A project, an exact version, a public evidence URL, and a policy are registered on the contract.",
  },
  {
    title: "Evidence",
    body: "The contract fetches the public record and extracts the facts each requested policy needs.",
  },
  {
    title: "Consensus",
    body: "GenLayer validators independently evaluate the evidence and must agree on the outcome.",
  },
  {
    title: "Verdict",
    body: "Contract logic composes the final decision deterministically. Missing evidence fails closed.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4">
      {/* Hero */}
      <section className="py-16 sm:py-20">
        <p className="eyebrow">
          GenLayer Studionet · public read-only console
        </p>
        <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
          Evidence-based release verification on GenLayer.
        </h1>
        <p className="lede mt-6 max-w-2xl">
          ReleaseGuard evaluates a software release against source, license, and
          vulnerability policies, then GenLayer consensus produces a single
          verdict: <span className="mono">VERIFIED</span>,{" "}
          <span className="mono">REJECTED</span>, or{" "}
          <span className="mono">INCONCLUSIVE</span>. This console reads those
          stored results from the deployed contract — it never connects a wallet
          or submits a transaction.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <Link
            href={`/inspect?id=${EXAMPLE.verificationId}`}
            className="btn btn-primary"
          >
            Verify a result <span aria-hidden="true">→</span>
          </Link>
          <Link href="/guide" className="btn btn-secondary">
            How a verification is created
          </Link>
        </div>
      </section>

      {/* Verdict legend */}
      <section aria-labelledby="legend" className="rule-t py-14">
        <p className="section-label" data-index="01">
          What the verdicts mean
        </p>
        <h2 id="legend" className="mt-4 text-2xl font-semibold sm:text-3xl">
          Three terminal outcomes, no ambiguity.
        </h2>
        <div className="mt-8">
          <VerdictLegend />
        </div>
      </section>

      {/* Verified example */}
      <section aria-labelledby="example" className="rule-t py-14">
        <p className="section-label" data-index="02">
          Verified example
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 id="example" className="text-2xl font-semibold sm:text-3xl">
            requests 2.31.0
          </h2>
          <VerdictBadge verdict="VERIFIED" size="sm" />
        </div>
        <p className="mt-4 max-w-2xl text-[0.9375rem] text-muted">
          A real verification record on the deployed contract, shown here as a
          concrete case rather than marketing copy. Inspect it live to see the
          per-check evidence the contract stored.
        </p>

        <div className="panel mt-8">
          <table className="data-table">
            <caption className="sr-only">
              Verified example record for requests 2.31.0
            </caption>
            <tbody>
              <tr>
                <th scope="row">Verification id</th>
                <td className="mono">{EXAMPLE.verificationId}</td>
              </tr>
              <tr>
                <th scope="row">Project</th>
                <td className="strong">{EXAMPLE.projectName}</td>
              </tr>
              <tr>
                <th scope="row">Version</th>
                <td className="mono">{EXAMPLE.version}</td>
              </tr>
              <tr>
                <th scope="row">Policy</th>
                <td className="mono">source, license</td>
              </tr>
              <tr>
                <th scope="row">Evidence URL</th>
                <td>
                  <ExternalLink href={EXAMPLE.evidenceUrl}>
                    {EXAMPLE.evidenceUrl}
                  </ExternalLink>
                </td>
              </tr>
              <tr>
                <th scope="row">Result</th>
                <td>
                  <span className="mono" style={{ color: "var(--color-verified)" }}>
                    source PASS · license PASS
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div className="flex flex-wrap gap-3 border-t border-line p-4">
            <Link
              href={`/inspect?id=${EXAMPLE.verificationId}`}
              className="btn btn-primary"
            >
              Inspect this result
            </Link>
            <ExternalLink
              href={EVIDENCE_LINKS.verifiedTx}
              className="btn btn-secondary"
            >
              Verified execution transaction
            </ExternalLink>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section aria-labelledby="how" className="rule-t py-14">
        <p className="section-label" data-index="03">
          How a verification is produced
        </p>
        <h2 id="how" className="mt-4 text-2xl font-semibold sm:text-3xl">
          From a claim to a consensus verdict.
        </h2>
        <div className="mt-8 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <div key={step.title}>
              <p className="mono" style={{ color: "var(--color-accent)" }}>
                {String(index + 1).padStart(2, "0")}
              </p>
              <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-[0.9375rem] text-muted">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Policy + fail-closed */}
      <section aria-labelledby="policies" className="rule-t py-14">
        <p className="section-label" data-index="04">
          Policies and the fail-closed rule
        </p>
        <h2 id="policies" className="mt-4 text-2xl font-semibold sm:text-3xl">
          Three checks, explicitly scoped.
        </h2>
        <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-start">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Policy</th>
                <th scope="col">Question it asks</th>
              </tr>
            </thead>
            <tbody>
              {SUPPORTED_POLICIES.map((policy) => (
                <tr key={policy.name}>
                  <td className="mono" style={{ color: "var(--color-accent-2)" }}>
                    {policy.name}
                  </td>
                  <td>{policy.help}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <Callout label="Fail closed">
            <p>
              Every requested policy must explicitly pass. If evidence is
              missing, a check cannot be evaluated, or consensus is not reached,
              the outcome is <span className="mono">INCONCLUSIVE</span> — never{" "}
              <span className="mono">VERIFIED</span>. Uncertainty cannot look
              safe.
            </p>
            <p className="mt-3">
              <span className="mono">VERIFIED</span> means the requested checks
              passed on the supplied evidence. It is not a security audit or a
              guarantee about the software.
            </p>
          </Callout>
        </div>
      </section>

      {/* Evidence */}
      <section id="evidence" aria-labelledby="evidence-heading" className="rule-t py-14">
        <p className="section-label" data-index="05">
          Public verification trail
        </p>
        <h2
          id="evidence-heading"
          className="mt-4 text-2xl font-semibold sm:text-3xl"
        >
          Inspect the evidence yourself.
        </h2>
        <p className="mt-4 max-w-2xl text-[0.9375rem] text-muted">
          The repository, the deployed contract, and a real verified execution
          are public on {NETWORK_NAME}.
        </p>
        <table className="data-table mt-8">
          <caption className="sr-only">
            Public evidence links for the ReleaseGuard deployment
          </caption>
          <tbody>
            <tr>
              <th scope="row">Source code</th>
              <td>
                <ExternalLink href={EVIDENCE_LINKS.github}>
                  github.com/Blue14352909/genlayer-release-guard
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">Studio deployment</th>
              <td>
                <ExternalLink href={EVIDENCE_LINKS.deployTx}>
                  Deployment transaction
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">Verified execution</th>
              <td>
                <ExternalLink href={EVIDENCE_LINKS.verifiedTx}>
                  VERIFIED execution transaction
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">Deployed contract</th>
              <td>
                <ExternalLink href={addressUrl(CONTRACT_ADDRESS)}>
                  <span className="mono break-all">{CONTRACT_ADDRESS}</span>
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">GenLayer Studio</th>
              <td>
                <ExternalLink href={STUDIO_IMPORT_URL}>
                  Open the contract in Studio
                </ExternalLink>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
