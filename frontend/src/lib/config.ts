import { studionet } from "genlayer-js/chains";

/**
 * ReleaseGuard frontend configuration.
 *
 * The contract address is read from the public environment variable
 * NEXT_PUBLIC_RELEASE_GUARD_ADDRESS. If it is missing or malformed we fall
 * back to the known Studionet deployment recorded in the repository README so
 * the app remains usable. It is never a secret.
 */
export const DEFAULT_CONTRACT_ADDRESS =
  "0xfFa341Ad1AC8aD5DB23405767be481eDDc8f5a46";

const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

function resolveContractAddress(): `0x${string}` {
  const raw = process.env.NEXT_PUBLIC_RELEASE_GUARD_ADDRESS?.trim();
  if (raw && ADDRESS_RE.test(raw)) {
    return raw as `0x${string}`;
  }
  return DEFAULT_CONTRACT_ADDRESS as `0x${string}`;
}

/** True when the env var was missing/invalid and the fallback is in use. */
export const USING_FALLBACK_ADDRESS: boolean = !(
  process.env.NEXT_PUBLIC_RELEASE_GUARD_ADDRESS?.trim() &&
  ADDRESS_RE.test(process.env.NEXT_PUBLIC_RELEASE_GUARD_ADDRESS.trim())
);

export const CONTRACT_ADDRESS = resolveContractAddress();

/** The GenLayer chain definition (imported from the SDK, not hand-rolled). */
export const CHAIN = studionet;
export const CHAIN_ID = studionet.id;
export const CHAIN_ID_HEX = `0x${studionet.id.toString(16)}`;
export const NETWORK_NAME = "GenLayer Studionet";

/** Block explorer base used for transaction links. */
export const EXPLORER_BASE = "https://explorer-studio.genlayer.com";

export function txUrl(hash: string): string {
  return `${EXPLORER_BASE}/tx/${hash}`;
}

export function addressUrl(address: string): string {
  return `${EXPLORER_BASE}/address/${address}`;
}

/** Policy names the orchestrator actually wires. Anything else fails closed. */
export const SUPPORTED_POLICIES = [
  {
    name: "source",
    label: "Source Attestation",
    help: "Does the evidence URL actually contain the claimed release?",
  },
  {
    name: "license",
    label: "License Check",
    help: "Is the observed project license permissive?",
  },
  {
    name: "vulnerability",
    label: "Vulnerability Check",
    help: "Are there known critical or high severity advisories?",
  },
] as const;

export type PolicyName = (typeof SUPPORTED_POLICIES)[number]["name"];

export const POLICY_NAMES: readonly PolicyName[] = SUPPORTED_POLICIES.map(
  (p) => p.name,
);

/** Prefilled example that resolves to a real, already-decided verification. */
export const EXAMPLE = {
  projectName: "requests",
  version: "2.31.0",
  evidenceUrl: "https://pypi.org/project/requests/2.31.0/",
  policies: ["source", "license"] as PolicyName[],
  /** A real on-chain verification id on the deployed Studionet contract. */
  verificationId: "v-1",
};

/** Public evidence links shown on the home page. */
export const EVIDENCE_LINKS = {
  github: "https://github.com/Blue14352909/genlayer-release-guard",
  deployTx:
    "https://explorer-studio.genlayer.com/tx/0xf0be08268d6d471a2316670a53ff7971db64204e00348a22e9fc77f73cb4a73e",
  verifiedTx:
    "https://explorer-studio.genlayer.com/tx/0xf13317be4cb28b184e5521eda04f02ca45fcb0612edbf9c1013f954d9b6e3f2b",
};
