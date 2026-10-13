import { sanitizeText } from "@/lib/format";

type Tone = {
  label: string;
  mark: string;
  color: string;
  background: string;
  border: string;
};

function toneFor(verdict: string): Tone {
  switch (verdict) {
    case "VERIFIED":
      return {
        label: "VERIFIED",
        mark: "✓",
        color: "var(--color-verified)",
        background: "var(--color-verified-soft)",
        border: "var(--color-verified-line)",
      };
    case "REJECTED":
      return {
        label: "REJECTED",
        mark: "✕",
        color: "var(--color-rejected)",
        background: "var(--color-rejected-soft)",
        border: "var(--color-rejected-line)",
      };
    case "INCONCLUSIVE":
      return {
        label: "INCONCLUSIVE",
        mark: "?",
        color: "var(--color-inconclusive)",
        background: "var(--color-inconclusive-soft)",
        border: "var(--color-inconclusive-line)",
      };
    case "PENDING":
    case "RUNNING":
      return {
        label: verdict,
        mark: "…",
        color: "var(--color-pending)",
        background: "var(--color-pending-soft)",
        border: "var(--color-pending-line)",
      };
    default:
      return {
        label: sanitizeText(verdict, 32) || "UNKNOWN",
        mark: "·",
        color: "var(--color-pending)",
        background: "var(--color-pending-soft)",
        border: "var(--color-pending-line)",
      };
  }
}

export function VerdictBadge({
  verdict,
  size = "md",
}: {
  verdict: string;
  size?: "sm" | "md" | "lg";
}) {
  const tone = toneFor(verdict);
  const sizeClass =
    size === "lg"
      ? "px-3.5 py-1.5 text-base"
      : size === "sm"
        ? "px-2 py-0.5 text-sm"
        : "px-2.5 py-1 text-sm";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-sm border font-semibold tracking-wide ${sizeClass}`}
      style={{
        color: tone.color,
        backgroundColor: tone.background,
        borderColor: tone.border,
      }}
    >
      <span aria-hidden="true" className="font-mono leading-none">
        {tone.mark}
      </span>
      {tone.label}
    </span>
  );
}
