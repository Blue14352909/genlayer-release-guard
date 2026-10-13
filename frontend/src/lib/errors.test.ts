import { describe, expect, it } from "vitest";
import { normalizeError } from "./errors";

describe("normalizeError", () => {
  it("maps a verification-not-found error to a helpful title", () => {
    const out = normalizeError(new Error("verification not found"));
    expect(out.title).toBe("No such verification");
    expect(out.detail).toMatch(/does not exist|no verification/i);
  });

  it("maps a network failure to a connection message", () => {
    const out = normalizeError(new Error("fetch failed"));
    expect(out.title).toBe("Could not reach the network");
  });

  it("maps a browser 'Failed to fetch' (CORS) error to a connection message", () => {
    const out = normalizeError(
      new Error("An unknown RPC error occurred. Details: Failed to fetch"),
    );
    expect(out.title).toBe("Could not reach the network");
  });

  it("maps a contract/gen_call failure to a rejection message", () => {
    const out = normalizeError(new Error("GenLayer RPC error (gen_call): execution failed"));
    expect(out.title).toBe("The contract rejected the read");
  });

  it("returns a generic message for nullish input", () => {
    const out = normalizeError(null);
    expect(out.title).toBe("Something went wrong");
    expect(out.detail.length).toBeGreaterThan(0);
  });

  it("bounds and surfaces an unknown message", () => {
    const out = normalizeError(new Error("kaboom"));
    expect(out.title).toBe("Request failed");
    expect(out.detail).toBe("kaboom");
  });
});
