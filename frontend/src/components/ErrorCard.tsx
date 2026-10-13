import type { ReactNode } from "react";
import { sanitizeText } from "@/lib/format";

export function ErrorCard({
  title,
  detail,
  action,
  children,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="panel panel-pad"
      style={{ borderColor: "var(--color-rejected-line)" }}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-sm font-mono text-sm font-bold"
          style={{
            color: "var(--color-rejected)",
            backgroundColor: "var(--color-rejected-soft)",
          }}
        >
          !
        </span>
        <div className="min-w-0 flex-1">
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--color-rejected)" }}
          >
            {sanitizeText(title, 120)}
          </h2>
          <p className="mt-1 text-[0.9375rem] break-words text-muted">
            {sanitizeText(detail, 600)}
          </p>
          {children ? <div className="mt-3">{children}</div> : null}
          {action ? (
            <div className="mt-4 flex flex-wrap gap-2">{action}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
