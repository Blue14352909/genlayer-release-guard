import { describe, expect, it } from "vitest";
import { checkStatusLabel, isHttpsUrl, sanitizeText, truncateMiddle } from "./format";

describe("isHttpsUrl", () => {
  it("accepts well-formed https URLs", () => {
    expect(isHttpsUrl("https://pypi.org/project/requests/2.31.0/")).toBe(true);
  });

  it("rejects http, javascript and relative inputs", () => {
    expect(isHttpsUrl("http://example.com")).toBe(false);
    expect(isHttpsUrl("javascript:alert(1)")).toBe(false);
    expect(isHttpsUrl("/relative/path")).toBe(false);
    expect(isHttpsUrl("not a url")).toBe(false);
  });

  it("rejects empty and whitespace input", () => {
    expect(isHttpsUrl("")).toBe(false);
    expect(isHttpsUrl("   ")).toBe(false);
  });

  it("trims surrounding whitespace before validating", () => {
    expect(isHttpsUrl("  https://example.com  ")).toBe(true);
  });
});

describe("sanitizeText", () => {
  it("strips control characters and collapses whitespace", () => {
    expect(sanitizeText("a\u0000b\t\t\tc")).toBe("a b  c");
  });

  it("caps very long strings with an ellipsis", () => {
    const out = sanitizeText("x".repeat(50), 10);
    expect(out).toBe(`${"x".repeat(10)}…`);
  });

  it("returns an empty string for nullish input", () => {
    expect(sanitizeText(null)).toBe("");
    expect(sanitizeText(undefined)).toBe("");
  });
});

describe("checkStatusLabel", () => {
  it("maps known statuses to readable labels", () => {
    expect(checkStatusLabel("PASS")).toBe("PASS");
    expect(checkStatusLabel("FETCH_FAILED")).toBe("FETCH FAILED");
    expect(checkStatusLabel("INSUFFICIENT_EVIDENCE")).toBe(
      "INSUFFICIENT EVIDENCE",
    );
  });

  it("falls back to UNKNOWN for an empty status", () => {
    expect(checkStatusLabel("")).toBe("UNKNOWN");
  });
});

describe("truncateMiddle", () => {
  it("shortens long values and leaves short values intact", () => {
    expect(truncateMiddle("0x1234567890abcdef", 6, 4)).toBe("0x1234…cdef");
    expect(truncateMiddle("short")).toBe("short");
  });
});
