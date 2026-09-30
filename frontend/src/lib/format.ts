/**
 * Formatting and sanitization helpers.
 *
 * React escapes text nodes by default, so these helpers are not an XSS
 * boundary — they exist to keep contract/evidence text readable, bounded in
 * size, and free of control characters. The app never renders raw HTML.
 */

/** Shorten a long hash or address for display: 0x1234…abcd */
export function truncateMiddle(value: string, head = 6, tail = 4): string {
  const v = String(value ?? "");
  if (v.length <= head + tail + 1) return v;
  return `${v.slice(0, head)}…${v.slice(-tail)}`;
}

const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;

/**
 * Coerce any value into a bounded, display-safe string.
 * Strips control characters, collapses runaway whitespace, and caps length.
 */
export function sanitizeText(value: unknown, maxLength = 2000): string {
  if (value === null || value === undefined) return "";
  let text = typeof value === "string" ? value : String(value);
  text = text.replace(CONTROL_CHARS, " ");
  text = text.replace(/\r\n?/g, "\n");
  text = text.replace(/[ \t]{3,}/g, "  ");
  text = text.replace(/\n{3,}/g, "\n\n");
  text = text.trim();
  if (text.length > maxLength) {
    text = `${text.slice(0, maxLength)}…`;
  }
  return text;
}

/** Validate an https URL client-side. This does NOT prove source safety. */
export function isHttpsUrl(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  let parsed: URL;
  try {
    parsed = new URL(v);
  } catch {
    return false;
  }
  return parsed.protocol === "https:" && Boolean(parsed.hostname);
}

/** Human label for a check status. */
export function checkStatusLabel(status: string): string {
  switch (status) {
    case "PASS":
      return "PASS";
    case "FAIL":
      return "FAIL";
    case "FETCH_FAILED":
      return "FETCH FAILED";
    case "INSUFFICIENT_EVIDENCE":
      return "INSUFFICIENT EVIDENCE";
    default:
      return sanitizeText(status, 40) || "UNKNOWN";
  }
}
