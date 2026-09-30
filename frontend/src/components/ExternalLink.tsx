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
      <span aria-hidden="true" className="ml-1 text-[0.7em] opacity-70">
        ↗
      </span>
    </a>
  );
}
