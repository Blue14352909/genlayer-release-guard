import { CheckStatusBadge } from "./CheckStatusBadge";
import { sanitizeText } from "@/lib/format";
import type { CheckResult } from "@/lib/types";

/**
 * Renders the individual check results returned by `get_check_results`.
 * Falls back to a meaningful empty state when the contract returns no checks.
 */
export function CheckResultsList({ results }: { results: CheckResult[] }) {
  if (results.length === 0) {
    return (
      <p className="text-[0.9375rem] text-muted">
        The contract returned no individual check results for this verification.
      </p>
    );
  }

  return (
    <ul className="grid gap-3">
      {results.map((result, index) => (
        <li key={`${result.check_name}-${index}`} className="panel panel-pad">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="mono" style={{ color: "var(--color-accent-2)" }}>
              {sanitizeText(result.check_name, 40)}
            </span>
            <CheckStatusBadge status={result.status} />
          </div>
          {result.evidence ? (
            <p className="mt-3 text-[0.9375rem]">
              <span className="text-muted">Evidence: </span>
              {sanitizeText(result.evidence, 400)}
            </p>
          ) : null}
          {result.reason ? (
            <p className="mt-1 text-[0.9375rem]">
              <span className="text-muted">Reason: </span>
              {sanitizeText(result.reason, 600)}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
