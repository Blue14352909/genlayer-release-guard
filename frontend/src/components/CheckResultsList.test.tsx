import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CheckResultsList } from "./CheckResultsList";
import type { CheckResult } from "@/lib/types";

const RESULTS: CheckResult[] = [
  {
    check_name: "source",
    status: "PASS",
    evidence: "requests 2.31.0",
    reason: "Project match=True, version match=True",
  },
  {
    check_name: "license",
    status: "FAIL",
    evidence: "GPL-3.0",
    reason: "not permissive",
  },
];

describe("CheckResultsList", () => {
  it("renders the empty state when there are no results", () => {
    render(<CheckResultsList results={[]} />);
    expect(
      screen.getByText(/no individual check results/i),
    ).toBeInTheDocument();
  });

  it("renders each check with name, status, evidence and reason", () => {
    render(<CheckResultsList results={RESULTS} />);
    expect(screen.getByText("source")).toBeInTheDocument();
    expect(screen.getByText("license")).toBeInTheDocument();
    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText(/requests 2\.31\.0/)).toBeInTheDocument();
    expect(screen.getByText(/not permissive/)).toBeInTheDocument();
  });

  it("omits evidence/reason lines when the contract returns none", () => {
    render(
      <CheckResultsList
        results={[{ check_name: "source", status: "PASS", evidence: "", reason: "" }]}
      />,
    );
    expect(screen.queryByText(/Evidence:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Reason:/)).not.toBeInTheDocument();
  });
});
