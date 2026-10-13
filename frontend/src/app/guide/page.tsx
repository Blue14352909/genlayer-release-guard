import Link from "next/link";
import { Callout } from "@/components/Callout";
import { ExternalLink } from "@/components/ExternalLink";
import {
  CONTRACT_ADDRESS,
  CONTRACT_METHODS,
  EVIDENCE_LINKS,
  EXAMPLE,
  STUDIO_IMPORT_URL,
  STUDIO_URL,
  SUPPORTED_POLICIES,
} from "@/lib/config";

const STUDIO_STEPS = [
  {
    title: "Deploy or open the contract",
    body: "Use the deployed ReleaseGuard contract on GenLayer Studionet, or import it into Studio with the address below. The Console itself never deploys anything.",
  },
  {
    title: "Call create_verification",
    body: "Register the claim: project name, exact version, a stable HTTPS evidence URL, and the comma-separated policy text. The call returns the new verification id.",
  },
  {
    title: "Call run_verification",
    body: "Pass the verification id. The contract fetches the evidence, runs the requested checks through consensus, and stores the outcome.",
  },
  {
    title: "Call get_verification",
    body: "Read the stored record back: project, version, policy, request status, verdict, reason code, failed checks, and per-check results.",
  },
  {
    title: "Inspect the Explorer transaction",
    body: "Open the transaction on the GenLayer Studio explorer to confirm the execution and its result independently.",
  },
];

export default function GuidePage() {
  const examplePolicyText = EXAMPLE.policies.join(",");

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <header>
        <p className="eyebrow">New verification</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">
          How a verification is created.
        </h1>
        <p className="lede mt-3">
          This page is guidance only. ReleaseGuard Console does not submit
          transactions or request a wallet — it documents the exact sequence to
          run in GenLayer Studio and then inspect here.
        </p>
      </header>

      <div className="mt-8">
        <Callout label="Read-only console">
          <p>
            Creating and running a verification are on-chain writes that require
            a funded Studionet account and a wallet signature. Do them in{" "}
            <ExternalLink href={STUDIO_IMPORT_URL}>GenLayer Studio</ExternalLink>
            , then return here to read the stored result. The Console only ever
            performs free reads.
          </p>
        </Callout>
      </div>

      <section aria-labelledby="sequence" className="mt-14">
        <p className="section-label" data-index="01">
          Studio sequence
        </p>
        <h2 id="sequence" className="mt-4 text-2xl font-semibold">
          Five steps, in order.
        </h2>
        <ol className="steps mt-8">
          {STUDIO_STEPS.map((step) => (
            <li key={step.title}>
              <h3 className="text-lg font-semibold">{step.title}</h3>
              <p className="mt-1 text-[0.9375rem] text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="methods" className="rule-t mt-14 py-12">
        <p className="section-label" data-index="02">
          Contract methods
        </p>
        <h2 id="methods" className="mt-4 text-2xl font-semibold">
          The exact interface.
        </h2>
        <table className="data-table mt-6">
          <thead>
            <tr>
              <th scope="col">Method</th>
              <th scope="col">Returns</th>
              <th scope="col">Role</th>
            </tr>
          </thead>
          <tbody>
            {CONTRACT_METHODS.map((method) => (
              <tr key={method.name}>
                <td>
                  <span className="mono break-all">{method.signature}</span>
                </td>
                <td className="mono">{method.returns}</td>
                <td>{method.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-4 text-[0.9375rem] text-muted">
          Deployed contract:{" "}
          <span className="mono break-all">{CONTRACT_ADDRESS}</span>
        </p>
      </section>

      <section aria-labelledby="policies" className="rule-t py-12">
        <p className="section-label" data-index="03">
          Supported policies
        </p>
        <h2 id="policies" className="mt-4 text-2xl font-semibold">
          source, license, vulnerability.
        </h2>
        <p className="mt-3 max-w-2xl text-[0.9375rem] text-muted">
          These three are the policies the orchestrator currently wires. Pass
          them as a comma-separated <span className="mono">policy_text</span>{" "}
          string. An unknown policy fails closed rather than being silently
          ignored.
        </p>
        <table className="data-table mt-6">
          <thead>
            <tr>
              <th scope="col">Policy</th>
              <th scope="col">What it evaluates</th>
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
      </section>

      <section aria-labelledby="fields" className="rule-t py-12">
        <p className="section-label" data-index="04">
          Field validation
        </p>
        <h2 id="fields" className="mt-4 text-2xl font-semibold">
          What a valid claim looks like.
        </h2>
        <ul className="mt-6 grid gap-3">
          <li className="panel panel-pad">
            <p className="font-semibold">Canonical project name</p>
            <p className="mt-1 text-[0.9375rem] text-muted">
              Use the name as published by the registry — for example{" "}
              <span className="mono">requests</span>, not a nickname.
            </p>
          </li>
          <li className="panel panel-pad">
            <p className="font-semibold">Exact version</p>
            <p className="mt-1 text-[0.9375rem] text-muted">
              The released version the evidence page is for, e.g.{" "}
              <span className="mono">{EXAMPLE.version}</span>.
            </p>
          </li>
          <li className="panel panel-pad">
            <p className="font-semibold">Stable evidence URL</p>
            <p className="mt-1 text-[0.9375rem] text-muted">
              A public HTTPS page that actually contains the release, e.g.{" "}
              <ExternalLink href={EXAMPLE.evidenceUrl}>
                {EXAMPLE.evidenceUrl}
              </ExternalLink>
              . The URL must contain evidence for every requested policy.
            </p>
          </li>
          <li className="panel panel-pad">
            <p className="font-semibold">Comma-separated policies</p>
            <p className="mt-1 text-[0.9375rem] text-muted">
              Only supported names, lower case, no spaces required — e.g.{" "}
              <span className="mono">{examplePolicyText}</span>.
            </p>
          </li>
        </ul>
      </section>

      <section aria-labelledby="inconclusive" className="rule-t py-12">
        <p className="section-label" data-index="05">
          Reading the outcome
        </p>
        <h2 id="inconclusive" className="mt-4 text-2xl font-semibold">
          INCONCLUSIVE is a fail-closed result.
        </h2>
        <div className="mt-6">
          <Callout label="Fail closed">
            <p>
              <span className="mono">INCONCLUSIVE</span> means the evidence or
              the consensus was insufficient to reach a confident decision. It
              is not a soft pass: a release that could not be evaluated did not
              pass, and it never resolves to{" "}
              <span className="mono">VERIFIED</span> on that basis.
            </p>
          </Callout>
        </div>
      </section>

      <div className="rule-t flex flex-wrap gap-3 py-10">
        <Link
          href={`/inspect?id=${EXAMPLE.verificationId}`}
          className="btn btn-primary"
        >
          Verify a result <span aria-hidden="true">→</span>
        </Link>
        <ExternalLink href={STUDIO_URL} className="btn btn-secondary">
          Open GenLayer Studio
        </ExternalLink>
        <ExternalLink href={EVIDENCE_LINKS.github} className="btn btn-secondary">
          Contract source
        </ExternalLink>
      </div>
    </div>
  );
}
