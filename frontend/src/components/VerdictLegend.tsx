import { VerdictBadge } from "./VerdictBadge";

const ROWS: Array<{ verdict: string; meaning: string }> = [
  {
    verdict: "VERIFIED",
    meaning: "Every requested check explicitly passed on the supplied evidence.",
  },
  {
    verdict: "REJECTED",
    meaning: "At least one requested check failed.",
  },
  {
    verdict: "INCONCLUSIVE",
    meaning:
      "Evidence or consensus was insufficient to decide. It fails closed — it never means the release passed.",
  },
];

/** Compact legend of the three terminal verdicts with their exact meanings. */
export function VerdictLegend() {
  return (
    <dl className="rule-t">
      {ROWS.map((row) => (
        <div
          key={row.verdict}
          className="flex flex-col gap-2 border-b border-line py-4 sm:flex-row sm:items-start sm:gap-6"
        >
          <dt className="sm:w-44 sm:shrink-0">
            <VerdictBadge verdict={row.verdict} />
          </dt>
          <dd className="text-[0.9375rem] text-muted">{row.meaning}</dd>
        </div>
      ))}
    </dl>
  );
}
