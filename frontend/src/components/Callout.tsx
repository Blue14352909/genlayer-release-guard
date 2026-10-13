import type { ReactNode } from "react";

export function Callout({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div
      className="panel-quiet panel-pad"
      style={{ borderLeft: "3px solid var(--color-accent)" }}
    >
      <p className="eyebrow">{label}</p>
      <div className="mt-2 text-[0.9375rem] leading-relaxed text-ink">
        {children}
      </div>
    </div>
  );
}
