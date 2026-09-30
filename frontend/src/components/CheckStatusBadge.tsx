import { checkStatusLabel } from "@/lib/format";

function colors(status: string): { color: string; border: string; bg: string } {
  switch (status) {
    case "PASS":
      return {
        color: "var(--color-verified)",
        border: "rgba(163, 230, 53, 0.45)",
        bg: "rgba(163, 230, 53, 0.12)",
      };
    case "FAIL":
      return {
        color: "var(--color-rejected)",
        border: "rgba(248, 113, 113, 0.45)",
        bg: "rgba(248, 113, 113, 0.12)",
      };
    case "FETCH_FAILED":
    case "INSUFFICIENT_EVIDENCE":
      return {
        color: "var(--color-inconclusive)",
        border: "rgba(251, 191, 36, 0.45)",
        bg: "rgba(251, 191, 36, 0.12)",
      };
    default:
      return {
        color: "var(--color-muted)",
        border: "rgba(147, 164, 196, 0.35)",
        bg: "rgba(147, 164, 196, 0.1)",
      };
  }
}

export function CheckStatusBadge({ status }: { status: string }) {
  const c = colors(status);
  return (
    <span
      className="inline-flex items-center rounded-md border px-2 py-0.5 text-[0.7rem] font-bold tracking-wide uppercase"
      style={{ color: c.color, borderColor: c.border, backgroundColor: c.bg }}
    >
      {checkStatusLabel(status)}
    </span>
  );
}
