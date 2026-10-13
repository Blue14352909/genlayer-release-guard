import { SUPPORTED_POLICIES, type PolicyName } from "./config";

/**
 * Policy-text helpers.
 *
 * The contract consumes `policy_text` as a comma-separated list of policy
 * names, e.g. `source,license`. These helpers parse, de-duplicate and describe
 * that string for display. They never assert that a policy passed — they only
 * report which names were requested and whether the orchestrator supports them.
 */

const SUPPORTED_SET: ReadonlySet<string> = new Set(
  SUPPORTED_POLICIES.map((p) => p.name),
);

const LABELS: Readonly<Record<string, string>> = Object.fromEntries(
  SUPPORTED_POLICIES.map((p) => [p.name, p.label]),
);

/** Split a policy string into trimmed, lower-cased, non-empty tokens. */
export function parsePolicyText(raw: string): string[] {
  return String(raw ?? "")
    .split(",")
    .map((token) => token.trim().toLowerCase())
    .filter((token) => token.length > 0);
}

/** Remove duplicate tokens while preserving first-seen order. */
export function uniquePolicies(tokens: readonly string[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const token of tokens) {
    if (!seen.has(token)) {
      seen.add(token);
      ordered.push(token);
    }
  }
  return ordered;
}

export function isSupportedPolicy(name: string): name is PolicyName {
  return SUPPORTED_SET.has(name);
}

/** Human label for a policy name, falling back to the raw token. */
export function policyLabel(name: string): string {
  return LABELS[name] ?? name;
}

export interface DescribedPolicy {
  name: string;
  label: string;
  supported: boolean;
}

/**
 * Parse `policy_text` into an ordered, de-duplicated list of described
 * policies. Unknown names are surfaced as `supported: false` rather than
 * dropped, because the contract fails closed on them.
 */
export function describePolicies(raw: string): DescribedPolicy[] {
  return uniquePolicies(parsePolicyText(raw)).map((name) => ({
    name,
    label: policyLabel(name),
    supported: isSupportedPolicy(name),
  }));
}

/** True when at least one requested policy is outside the supported set. */
export function hasUnsupportedPolicy(raw: string): boolean {
  return describePolicies(raw).some((p) => !p.supported);
}
