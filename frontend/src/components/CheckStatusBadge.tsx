import { checkStatusLabel } from "@/lib/format";

function tone(status: string): { color: string; border: string; bg: string } {
  switch (status) {
    case "PASS":
      return {
        color: "var(--color-verified)",
        border: "var(--color-verified-line)",
        bg: "var(--color-verified-soft)",
      };
    case "FAIL":
      return {
        color: "var(--color-rejected)",
        border: "var(--color-rejected-line)",
        bg: "var(--color-rejected-soft)",
      };
    case "FETCH_FAILED":
    case "INSUFFICIENT_EVIDENCE":
      return {
        color: "var(--color-inconclusive)",
        border: "var(--color-inconclusive-line)",
        bg: "var(--color-inconclusive-soft)",
      };
    default:
      return {
        color: "var(--color-pending)",
        border: "var(--color-pending-line)",
        bg: "var(--color-pending-soft)",
      };
  }
}

export function CheckStatusBadge({ status }: { status: string }) {
  const c = tone(status);
  return (
    <span
      className="inline-flex items-center rounded-sm border px-2 py-0.5 font-mono text-sm font-semibold"
      style={{ color: c.color, borderColor: c.border, backgroundColor: c.bg }}
    >
      {checkStatusLabel(status)}
    </span>
  );
}
