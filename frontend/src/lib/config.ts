import { studionet } from "genlayer-js/chains";

/**
 * ReleaseGuard Console — public configuration.
 *
 * The contract address is read from NEXT_PUBLIC_RELEASE_GUARD_ADDRESS. If it is
 * missing or malformed we fall back to the known Studionet deployment recorded
 * in the repository README so the app stays usable. It is never a secret.
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
export const NETWORK_NAME = "GenLayer Studionet";
export const STUDIO_URL = "https://studio.genlayer.com";

/** Block explorer base used for transaction and address links. */
export const EXPLORER_BASE = "https://explorer-studio.genlayer.com";

export function txUrl(hash: string): string {
  return `${EXPLORER_BASE}/tx/${hash}`;
}

export function addressUrl(address: string): string {
  return `${EXPLORER_BASE}/address/${address}`;
}

/** Open the deployed contract in GenLayer Studio. */
export const STUDIO_IMPORT_URL = `${STUDIO_URL}/?import-contract=${CONTRACT_ADDRESS}`;

/** Contract methods the Console documents and reads. */
export const CONTRACT_METHODS = [
  {
    name: "create_verification",
    signature: "create_verification(project_name, version, evidence_url, policy_text)",
    returns: "str",
    role: "Registers a new claim and returns its verification id.",
  },
  {
    name: "run_verification",
    signature: "run_verification(verification_id)",
    returns: "str",
    role: "Runs the requested checks through consensus and stores the outcome.",
  },
  {
    name: "get_verification",
    signature: "get_verification(verification_id)",
    returns: "dict",
    role: "Returns the stored record: project, version, policy, status, verdict.",
  },
  {
    name: "get_verdict",
    signature: "get_verdict(verification_id)",
    returns: "str",
    role: "Returns the consensus verdict for the record.",
  },
  {
    name: "get_check_results",
    signature: "get_check_results(verification_id)",
    returns: "list",
    role: "Returns each check's name, status, evidence and reason.",
  },
] as const;

/** Policy names the orchestrator actually wires. Anything else fails closed. */
export const SUPPORTED_POLICIES = [
  {
    name: "source",
    label: "Source",
    help: "Does the evidence URL actually contain the claimed release?",
  },
  {
    name: "license",
    label: "License",
    help: "Is the observed project license permissive?",
  },
  {
    name: "vulnerability",
    label: "Vulnerability",
    help: "Are there known critical or high severity advisories?",
  },
] as const;

export type PolicyName = (typeof SUPPORTED_POLICIES)[number]["name"];

export const POLICY_NAMES: readonly PolicyName[] = SUPPORTED_POLICIES.map(
  (p) => p.name,
);

/**
 * The verified example. `v-1` is a real, already-decided record on the deployed
 * Studionet contract. It is labelled "Verified example" wherever it appears.
 */
export const EXAMPLE = {
  projectName: "requests",
  version: "2.31.0",
  evidenceUrl: "https://pypi.org/project/requests/2.31.0/",
  policies: ["source", "license"] as PolicyName[],
  /** A real on-chain verification id on the deployed Studionet contract. */
  verificationId: "v-1",
} as const;

/** Public evidence links shown across the Console. */
export const EVIDENCE_LINKS = {
  github: "https://github.com/Blue14352909/genlayer-release-guard",
  deployTx:
    "https://explorer-studio.genlayer.com/tx/0xf0be08268d6d471a2316670a53ff7971db64204e00348a22e9fc77f73cb4a73e",
  verifiedTx:
    "https://explorer-studio.genlayer.com/tx/0xf13317be4cb28b184e5521eda04f02ca45fcb0612edbf9c1013f954d9b6e3f2b",
} as const;
