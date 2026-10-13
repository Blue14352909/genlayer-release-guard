import {
  CONTRACT_ADDRESS,
  EVIDENCE_LINKS,
  NETWORK_NAME,
  addressUrl,
} from "@/lib/config";
import { ExternalLink } from "./ExternalLink";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 sm:grid-cols-[1.3fr_1fr]">
        <div>
          <p className="font-semibold">ReleaseGuard Console</p>
          <p className="mt-2 max-w-md text-[0.9375rem] text-muted">
            A public, read-only workspace for inspecting release-verification
            results produced by the deployed ReleaseGuard contract on{" "}
            {NETWORK_NAME}. It is a Studionet demonstration and carries no
            legal, security, or fitness-for-purpose guarantee.
          </p>
        </div>
        <nav aria-label="Evidence" className="text-[0.9375rem]">
          <p className="mono text-muted">Evidence</p>
          <ul className="mt-3 space-y-2">
            <li>
              <ExternalLink href={EVIDENCE_LINKS.github}>
                GitHub repository
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={EVIDENCE_LINKS.deployTx}>
                Deployment transaction
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={EVIDENCE_LINKS.verifiedTx}>
                Verified execution transaction
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={addressUrl(CONTRACT_ADDRESS)}>
                Deployed contract
              </ExternalLink>
            </li>
          </ul>
        </nav>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-wrap gap-x-6 gap-y-1 px-4 py-4">
          <span className="mono text-muted">
            Contract {CONTRACT_ADDRESS}
          </span>
          <span className="mono text-muted">Network: {NETWORK_NAME}</span>
        </div>
      </div>
    </footer>
  );
}
