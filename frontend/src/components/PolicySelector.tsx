"use client";

import { SUPPORTED_POLICIES, type PolicyName } from "@/lib/config";

export function PolicySelector({
  selected,
  onToggle,
  disabled = false,
}: {
  selected: PolicyName[];
  onToggle: (policy: PolicyName) => void;
  disabled?: boolean;
}) {
  const policyText = selected.join(",");

  return (
    <fieldset>
      <legend className="label">Policy checks</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {SUPPORTED_POLICIES.map((policy) => {
          const checked = selected.includes(policy.name);
          return (
            <label
              key={policy.name}
              className="card flex cursor-pointer items-start gap-3 p-3 transition-colors"
              style={{
                borderColor: checked
                  ? "var(--color-accent)"
                  : "var(--color-line)",
              }}
            >
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 accent-cyan-400"
                checked={checked}
                disabled={disabled}
                onChange={() => onToggle(policy.name)}
              />
              <span className="min-w-0">
                <span className="block text-sm font-semibold">
                  {policy.label}
                </span>
                <span className="mt-0.5 block text-xs text-muted">
                  {policy.help}
                </span>
              </span>
            </label>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-muted">
        <code className="mono">policy_text</code> sent to the contract:{" "}
        <code
          className="mono"
          style={{
            color: policyText
              ? "var(--color-accent)"
              : "var(--color-inconclusive)",
          }}
        >
          {policyText || "(empty — the contract fails closed)"}
        </code>
      </p>
    </fieldset>
  );
}
