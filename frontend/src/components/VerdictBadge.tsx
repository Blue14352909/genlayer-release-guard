import { sanitizeText } from "@/lib/format";

type Tone = {
  label: string;
  color: string;
  background: string;
  border: string;
};

function toneFor(verdict: string): Tone {
  switch (verdict) {
    case "VERIFIED":
      return {
        label: "VERIFIED",
        color: "var(--color-verified)",
        background: "rgba(163, 230, 53, 0.12)",
        border: "rgba(163, 230, 53, 0.45)",
      };
    case "REJECTED":
      return {
        label: "REJECTED",
        color: "var(--color-rejected)",
        background: "rgba(248, 113, 113, 0.12)",
        border: "rgba(248, 113, 113, 0.45)",
      };
    case "INCONCLUSIVE":
      return {
        label: "INCONCLUSIVE",
        color: "var(--color-inconclusive)",
        background: "rgba(251, 191, 36, 0.12)",
        border: "rgba(251, 191, 36, 0.45)",
      };
    case "PENDING":
    case "RUNNING":
      return {
        label: verdict,
        color: "var(--color-pending)",
        background: "rgba(148, 163, 184, 0.12)",
        border: "rgba(148, 163, 184, 0.4)",
      };
    default:
      return {
        label: sanitizeText(verdict, 32) || "UNKNOWN",
        color: "var(--color-muted)",
        background: "rgba(147, 164, 196, 0.1)",
        border: "rgba(147, 164, 196, 0.35)",
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
  const pad =
    size === "lg"
      ? "px-4 py-1.5 text-base"
      : size === "sm"
        ? "px-2.5 py-0.5 text-xs"
        : "px-3 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border font-bold tracking-wide ${pad}`}
      style={{
        color: tone.color,
        backgroundColor: tone.background,
        borderColor: tone.border,
      }}
    >
      <span
        aria-hidden="true"
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: tone.color }}
      />
      {tone.label}
    </span>
  );
}
