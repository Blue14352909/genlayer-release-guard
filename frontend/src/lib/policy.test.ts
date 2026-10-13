import { describe, expect, it } from "vitest";
import {
  describePolicies,
  hasUnsupportedPolicy,
  isSupportedPolicy,
  parsePolicyText,
  policyLabel,
  uniquePolicies,
} from "./policy";

describe("parsePolicyText", () => {
  it("splits, trims and lower-cases a comma-separated policy string", () => {
    expect(parsePolicyText(" Source, License ")).toEqual([
      "source",
      "license",
    ]);
  });

  it("drops empty tokens", () => {
    expect(parsePolicyText("source,,license,")).toEqual(["source", "license"]);
  });

  it("returns an empty array for empty or nullish input", () => {
    expect(parsePolicyText("")).toEqual([]);
    expect(parsePolicyText(undefined as unknown as string)).toEqual([]);
  });
});

describe("uniquePolicies", () => {
  it("de-duplicates while preserving first-seen order", () => {
    expect(uniquePolicies(["license", "source", "license"])).toEqual([
      "license",
      "source",
    ]);
  });
});

describe("isSupportedPolicy / policyLabel", () => {
  it("recognises supported policy names", () => {
    expect(isSupportedPolicy("source")).toBe(true);
    expect(isSupportedPolicy("license")).toBe(true);
    expect(isSupportedPolicy("vulnerability")).toBe(true);
  });

  it("rejects unknown names", () => {
    expect(isSupportedPolicy("malware")).toBe(false);
    expect(isSupportedPolicy("Source")).toBe(false);
  });

  it("maps names to human labels and falls back to the raw token", () => {
    expect(policyLabel("source")).toBe("Source");
    expect(policyLabel("unknown")).toBe("unknown");
  });
});

describe("describePolicies", () => {
  it("describes supported policies in order", () => {
    expect(describePolicies("source,license")).toEqual([
      { name: "source", label: "Source", supported: true },
      { name: "license", label: "License", supported: true },
    ]);
  });

  it("surfaces unknown policies rather than dropping them", () => {
    const described = describePolicies("source,malware");
    expect(described).toHaveLength(2);
    expect(described[1]).toEqual({
      name: "malware",
      label: "malware",
      supported: false,
    });
    expect(hasUnsupportedPolicy("source,malware")).toBe(true);
    expect(hasUnsupportedPolicy("source,license")).toBe(false);
  });

  it("returns an empty list for an empty policy string", () => {
    expect(describePolicies("")).toEqual([]);
  });
});
