import { CONTRACT_ADDRESS, EVIDENCE_LINKS, NETWORK_NAME } from "@/lib/config";
import { ExternalLink } from "./ExternalLink";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:grid-cols-[1fr_auto]">
        <div>
          <p className="font-semibold">ReleaseGuard</p>
          <p className="mt-2 max-w-xl text-sm text-muted">
            This is a GenLayer <strong>Studionet demonstration</strong>.
            ReleaseGuard is an evidence-based, fail-closed release-attestation
            tool. It makes no legal, security, or fitness guarantee, and{" "}
            <strong>VERIFIED does not mean the software is objectively safe</strong>{" "}
            — it means every requested check explicitly passed against the
            evidence supplied at verification time.
          </p>
        </div>
        <div className="space-y-2 text-sm">
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">
            Evidence
          </p>
          <div>
            <ExternalLink href={EVIDENCE_LINKS.github}>
              GitHub repository
            </ExternalLink>
          </div>
          <div>
            <ExternalLink href={EVIDENCE_LINKS.deployTx}>
              Studio deployment transaction
            </ExternalLink>
          </div>
          <div>
            <ExternalLink href={EVIDENCE_LINKS.verifiedTx}>
              VERIFIED execution transaction
            </ExternalLink>
          </div>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap gap-x-5 gap-y-1 px-4 py-4 text-xs text-muted">
          <span>
            Contract <span className="mono">{CONTRACT_ADDRESS}</span>
          </span>
          <span>Network: {NETWORK_NAME}</span>
        </div>
      </div>
    </footer>
  );
}
