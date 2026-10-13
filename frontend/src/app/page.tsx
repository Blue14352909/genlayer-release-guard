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

const FLOW = [
  {
    label: "01",
    title: "Claim",
    body: "A project, version, public URL, and policy are submitted.",
  },
  {
    label: "02",
    title: "Evidence",
    body: "Validators independently evaluate the public record.",
  },
  {
    label: "03",
    title: "Consensus",
    body: "GenLayer establishes a shared outcome for the check.",
  },
  {
    label: "04",
    title: "Verdict",
    body: "Contract logic composes a fail-closed final decision.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4">
      <section className="hero-shell grid gap-12 py-16 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-24">
        <div>
          <p className="eyebrow">GenLayer Studionet · fail-closed attestation</p>
          <h1 className="mt-5 max-w-3xl text-5xl font-black tracking-[-0.055em] sm:text-6xl">
            Verify releases before you ship them.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-muted">
            ReleaseGuard turns public release evidence into an on-chain,
            consensus-backed decision—with no path from uncertainty to VERIFIED.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link href={`/inspect?id=${EXAMPLE.verificationId}`} className="btn btn-primary">
              Inspect a real result <span aria-hidden="true">→</span>
            </Link>
            <ExternalLink href={EVIDENCE_LINKS.verifiedTx} className="btn btn-secondary">View verified transaction</ExternalLink>
          </div>
          <p className="mt-5 max-w-lg text-xs leading-5 text-muted">
            This public demonstration is read-only. It never asks to connect a wallet.
          </p>
        </div>

        <aside className="receipt" aria-label="Live verified example">
          <div className="receipt-topline">
            <span className="eyebrow">Live Studionet example · v-1</span>
            <span className="status-verified">VERIFIED</span>
          </div>
          <div className="receipt-title-row">
            <div>
              <p className="receipt-name">requests</p>
              <p className="mono text-muted">version 2.31.0</p>
            </div>
            <span className="receipt-mark" aria-hidden="true">✓</span>
          </div>
          <div className="receipt-rule" />
          <dl className="receipt-list">
            <div><dt>POLICY</dt><dd className="mono">source, license</dd></div>
            <div><dt>SOURCE</dt><dd><span className="pass-dot" />PASS · requests 2.31.0</dd></div>
            <div><dt>LICENSE</dt><dd><span className="pass-dot" />PASS · Apache 2.0</dd></div>
            <div><dt>CONTRACT</dt><dd className="mono">0xfFa341…f5a46</dd></div>
          </dl>
          <Link href={`/inspect?id=${EXAMPLE.verificationId}`} className="receipt-link">
            Inspect this on-chain result <span aria-hidden="true">↗</span>
          </Link>
        </aside>
      </section>

      <section aria-labelledby="how" className="section-rule py-14">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">The verification path</p>
            <h2 id="how" className="mt-3 text-3xl font-bold tracking-[-0.04em]">Evidence, not assurance theatre.</h2>
          </div>
          <p className="max-w-sm text-sm leading-6 text-muted">Every requested policy must explicitly pass. Missing evidence and failed consensus stay non-verified.</p>
        </div>
        <div className="flow-grid mt-10">
          {FLOW.map((step) => (
            <div key={step.title} className="flow-step">
              <p className="mono flow-number">{step.label}</p>
              <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="checks" className="py-14">
        <div className="grid gap-8 lg:grid-cols-[0.7fr_1.3fr] lg:items-start">
          <div>
            <p className="eyebrow">Policy surface</p>
            <h2 id="checks" className="mt-3 text-3xl font-bold tracking-[-0.04em]">Three checks. Explicit scope.</h2>
            <p className="mt-4 max-w-sm text-sm leading-6 text-muted">The orchestrator wires only the policies below. An unknown policy fails closed rather than being silently ignored.</p>
          </div>
          <div className="policy-list">
          {SUPPORTED_POLICIES.map((policy) => (
            <div key={policy.name} className="policy-row">
              <p className="mono policy-code">{policy.name}</p>
              <div>
                <h3 className="font-semibold">{policy.label}</h3>
                <p className="mt-1 text-sm text-muted">{policy.help}</p>
              </div>
            </div>
          ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="failclosed" className="py-14">
        <div className="decision-panel">
          <div className="max-w-xl">
            <p className="eyebrow">Deterministic composition</p>
            <h2 id="failclosed" className="mt-3 text-3xl font-bold tracking-[-0.04em]">Fail closed means uncertainty cannot look safe.</h2>
            <p className="mt-4 text-sm leading-6 text-muted">ReleaseGuard does not use absence, malformed data, or a lack of consensus as a shortcut to a passing result.</p>
          </div>
          <div className="decision-table">
            <div><span className="mono">ALL REQUESTED CHECKS PASS</span><strong className="decision-verified">VERIFIED</strong></div>
            <div><span className="mono">ANY REQUESTED CHECK FAILS</span><strong className="decision-rejected">REJECTED</strong></div>
            <div><span className="mono">EVIDENCE OR CONSENSUS UNCLEAR</span><strong className="decision-inconclusive">INCONCLUSIVE</strong></div>
          </div>
        </div>
      </section>

      <section id="evidence" aria-labelledby="evidence-heading" className="section-rule py-14">
        <p className="eyebrow">Public verification trail</p>
        <h2 id="evidence-heading" className="mt-3 text-3xl font-bold tracking-[-0.04em]">Inspect the evidence yourself.</h2>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">The repository, deployed contract, and a real VERIFIED execution are public on {NETWORK_NAME}.</p>
        <div className="evidence-ledger mt-8">
          <div className="evidence-row">
            <p className="mono text-muted">SOURCE CODE</p>
            <p>
              <ExternalLink href={EVIDENCE_LINKS.github}>
                github.com/Blue14352909/genlayer-release-guard
              </ExternalLink>
            </p>
          </div>
          <div className="evidence-row">
            <p className="mono text-muted">STUDIO DEPLOYMENT</p>
            <p>
              <ExternalLink href={EVIDENCE_LINKS.deployTx}>
                Deployment transaction
              </ExternalLink>
            </p>
          </div>
          <div className="evidence-row">
            <p className="mono text-muted">VERIFIED EXECUTION</p>
            <p>
              <ExternalLink href={EVIDENCE_LINKS.verifiedTx}>
                VERIFIED execution transaction
              </ExternalLink>
            </p>
          </div>
          <div className="evidence-row">
            <p className="mono text-muted">DEPLOYED CONTRACT</p>
            <p className="mono break-all">
            <ExternalLink href={addressUrl(CONTRACT_ADDRESS)}>
              {CONTRACT_ADDRESS}
            </ExternalLink>
          </p>
          </div>
        </div>
      </section>
    </div>
  );
}
