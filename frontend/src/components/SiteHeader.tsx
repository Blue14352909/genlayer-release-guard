"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
const NAV = [
  { href: "/inspect", label: "Inspect Result" },
  { href: "/#evidence", label: "Evidence" },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href.startsWith("/#")) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function ShieldMark() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M12 2.6 4.8 5.4v5.5c0 4.3 3 8.2 7.2 9.5 4.2-1.3 7.2-5.2 7.2-9.5V5.4L12 2.6Z"
        stroke="var(--color-accent)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="m9 12 2.1 2.1L15.4 9.8"
        stroke="var(--color-accent-2)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2 rounded-md"
          aria-label="ReleaseGuard home"
        >
          <ShieldMark />
          <span className="text-[1.05rem] font-bold tracking-tight">
            ReleaseGuard
          </span>
        </Link>

        <nav
          aria-label="Primary"
          className="ml-auto hidden items-center gap-1 md:flex"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-muted transition-colors hover:text-fg"
              style={{
                color: isActive(pathname, item.href)
                  ? "var(--color-accent)"
                  : undefined,
              }}
            >
              {item.label}
            </Link>
          ))}
        </nav>

      </div>

      <nav
        aria-label="Primary mobile"
        className="flex items-center gap-1 overflow-x-auto border-t border-line px-3 py-2 md:hidden"
      >
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap text-muted transition-colors hover:text-fg"
            style={{
              color: isActive(pathname, item.href)
                ? "var(--color-accent)"
                : undefined,
            }}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
