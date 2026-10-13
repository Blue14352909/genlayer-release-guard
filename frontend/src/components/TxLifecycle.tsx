import { sanitizeText } from "@/lib/format";

export type StepState = "idle" | "active" | "done" | "error";

export interface LifecycleStep {
  key: string;
  label: string;
  detail?: string;
  state: StepState;
}

function dotColor(state: StepState): string {
  switch (state) {
    case "done":
      return "var(--color-verified)";
    case "active":
      return "var(--color-accent)";
    case "error":
      return "var(--color-rejected)";
    default:
      return "var(--color-line-strong)";
  }
}

export function TxLifecycle({ steps }: { steps: LifecycleStep[] }) {
  return (
    <ol className="space-y-3" aria-label="Transaction lifecycle">
      {steps.map((step) => (
        <li key={step.key} className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className="mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
            style={{
              backgroundColor: dotColor(step.state),
              boxShadow:
                step.state === "active"
                  ? "0 0 0 4px rgba(34, 211, 238, 0.18)"
                  : undefined,
            }}
          />
          <div className="min-w-0">
            <p
              className="text-sm font-medium"
              style={{
                color:
                  step.state === "idle"
                    ? "var(--color-muted)"
                    : "var(--color-fg)",
              }}
            >
              {sanitizeText(step.label, 120)}
            </p>
            {step.detail ? (
              <p className="mono mt-0.5 break-all text-muted">
                {sanitizeText(step.detail, 240)}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
