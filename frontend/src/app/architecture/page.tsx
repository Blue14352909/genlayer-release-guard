import { ExternalLink } from "@/components/ExternalLink";
import { VerdictLegend } from "@/components/VerdictLegend";
import {
  CONTRACT_ADDRESS,
  EVIDENCE_LINKS,
  EXPLORER_BASE,
  NETWORK_NAME,
  STUDIO_IMPORT_URL,
  addressUrl,
} from "@/lib/config";

const LAYERS = [
  {
    index: "A",
    title: "ReleaseGuard Console",
    role: "Display and inspection",
    body: "Routes, tables, and status rendering. It reads from the contract and formats the result. It holds no key, signs nothing, and submits nothing.",
  },
  {
    index: "B",
    title: "ReleaseGuard contract",
    role: "Verification logic and state",
    body: "The deployed intelligent contract stores each verification and decides the verdict. Its logic is the source of truth for every result shown here.",
  },
  {
    index: "C",
    title: "GenLayer consensus",
    role: "Non-deterministic evaluation",
    body: "Validators independently evaluate the public evidence and must agree. Their agreement — or its absence — is what the contract turns into a terminal verdict.",
  },
];

const GUARANTEES = [
  {
    label: "No wallet connection",
    body: "The Console never asks for a wallet, an account, or a signature.",
  },
  {
    label: "No transaction",
    body: "Nothing here submits, sets, or mutates on-chain state. Every action is a free read.",
  },
  {
    label: "No user data collected",
    body: "There is no login, no form that posts anywhere, and no client-side persistence of your input.",
  },
];

export default function ArchitecturePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <header>
        <p className="eyebrow">Architecture &amp; trust</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">
          Where each part of the result comes from.
        </h1>
        <p className="lede mt-3">
          ReleaseGuard Console is a thin, read-only layer over a deployed
          contract. Knowing the boundary makes the results easier to trust — and
          easier to check yourself.
        </p>
      </header>

      <section aria-labelledby="boundary" className="mt-12">
        <p className="section-label" data-index="01">
          The boundary
        </p>
        <h2 id="boundary" className="mt-4 text-2xl font-semibold">
          Three layers, one direction of trust.
        </h2>
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          {LAYERS.map((layer) => (
            <div key={layer.index} className="panel panel-pad">
              <p className="mono" style={{ color: "var(--color-accent)" }}>
                {layer.index}
              </p>
              <h3 className="mt-3 text-lg font-semibold">{layer.title}</h3>
              <p className="mono mt-1 text-muted">{layer.role}</p>
              <p className="mt-3 text-[0.9375rem] text-muted">{layer.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="safe" className="rule-t mt-12 py-12">
        <p className="section-label" data-index="02">
          What the website does not do
        </p>
        <h2 id="safe" className="mt-4 text-2xl font-semibold">
          Safe by remaining read-only.
        </h2>
        <table className="data-table mt-6">
          <thead>
            <tr>
              <th scope="col">Property</th>
              <th scope="col">Guarantee</th>
            </tr>
          </thead>
          <tbody>
            {GUARANTEES.map((item) => (
              <tr key={item.label}>
                <td className="strong">{item.label}</td>
                <td>{item.body}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="verdicts" className="rule-t py-12">
        <p className="section-label" data-index="03">
          Verdicts
        </p>
        <h2 id="verdicts" className="mt-4 text-2xl font-semibold">
          Composed deterministically.
        </h2>
        <p className="mt-3 max-w-2xl text-[0.9375rem] text-muted">
          The contract composes the final verdict from the individual checks. No
          model decides the verdict itself; consensus decides each check, and
          the composition rule decides the outcome.
        </p>
        <div className="mt-6">
          <VerdictLegend />
        </div>
      </section>

      <section aria-labelledby="verify" className="rule-t py-12">
        <p className="section-label" data-index="04">
          Verify it directly
        </p>
        <h2 id="verify" className="mt-4 text-2xl font-semibold">
          Read the contract yourself.
        </h2>
        <table className="data-table mt-6">
          <tbody>
            <tr>
              <th scope="row">Contract</th>
              <td>
                <ExternalLink href={addressUrl(CONTRACT_ADDRESS)}>
                  <span className="mono break-all">{CONTRACT_ADDRESS}</span>
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">Network</th>
              <td>{NETWORK_NAME}</td>
            </tr>
            <tr>
              <th scope="row">Source</th>
              <td>
                <ExternalLink href={EVIDENCE_LINKS.github}>
                  github.com/Blue14352909/genlayer-release-guard
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">Studio</th>
              <td>
                <ExternalLink href={STUDIO_IMPORT_URL}>
                  Open the contract in GenLayer Studio
                </ExternalLink>
              </td>
            </tr>
            <tr>
              <th scope="row">Explorer</th>
              <td>
                <ExternalLink href={EXPLORER_BASE}>
                  {EXPLORER_BASE.replace("https://", "")}
                </ExternalLink>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
