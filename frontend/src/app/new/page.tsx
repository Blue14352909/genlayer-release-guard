import Link from "next/link";
import { EXAMPLE, NETWORK_NAME } from "@/lib/config";

export default function NewVerificationPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-20">
      <p className="eyebrow">Public demonstration</p>
      <h1 className="mt-4 text-4xl font-black tracking-[-0.05em]">
        Read-only verification explorer
      </h1>
      <p className="mt-5 max-w-2xl text-lg leading-8 text-muted">
        This Vercel deployment is intentionally read-only. It provides public
        access to the deployed ReleaseGuard contract and its evidence without
        requesting a wallet connection or transaction signature.
      </p>
      <div className="mt-9 flex flex-wrap gap-3">
        <Link href={`/inspect?id=${EXAMPLE.verificationId}`} className="btn btn-primary">
          Inspect the VERIFIED example <span aria-hidden="true">→</span>
        </Link>
        <Link href="/" className="btn btn-secondary">
          Return home
        </Link>
      </div>
      <p className="mt-6 text-sm text-muted">
        Network: {NETWORK_NAME}. No wallet connection is available in this demo.
      </p>
    </div>
  );
}
