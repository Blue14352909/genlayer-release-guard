import type { ReactNode } from "react";

export function ExternalLink({
  href,
  children,
  className = "link",
  title,
}: {
  href: string;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      title={title}
    >
      {children}
      <span
        aria-hidden="true"
        className="ml-1 align-middle font-mono text-[0.85em] opacity-70"
      >
        ↗
      </span>
    </a>
  );
}
