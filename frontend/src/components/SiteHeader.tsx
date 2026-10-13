"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/inspect", label: "Verify a result" },
  { href: "/guide", label: "New verification" },
  { href: "/architecture", label: "Architecture" },
] as const;

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Mark() {
  return (
    <svg
      width="22"
      height="22"
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
        d="m8.9 12 2.1 2.1 4.1-4.3"
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
    <header className="sticky top-0 z-40 border-b border-line bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-5xl items-center gap-4 px-4">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2.5"
          aria-label="ReleaseGuard Console home"
        >
          <Mark />
          <span className="flex flex-col leading-none">
            <span className="text-[1.0625rem] font-semibold tracking-tight">
              ReleaseGuard
            </span>
            <span className="mono text-muted">Console</span>
          </span>
        </Link>

        <nav
          aria-label="Primary"
          className="ml-auto hidden items-center gap-1 md:flex"
        >
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className="rounded-sm px-3 py-2 text-sm font-medium text-muted transition-colors hover:text-ink"
                style={active ? { color: "var(--color-accent-2)" } : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <nav
        aria-label="Primary mobile"
        className="flex items-center gap-1 overflow-x-auto border-t border-line px-3 py-2 md:hidden"
      >
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className="rounded-sm px-3 py-1.5 text-sm font-medium whitespace-nowrap text-muted"
              style={active ? { color: "var(--color-accent-2)" } : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
