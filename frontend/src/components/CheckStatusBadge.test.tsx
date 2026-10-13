import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CheckStatusBadge } from "./CheckStatusBadge";

describe("CheckStatusBadge", () => {
  it("renders PASS as a text label", () => {
    render(<CheckStatusBadge status="PASS" />);
    expect(screen.getByText("PASS")).toBeInTheDocument();
  });

  it("renders FAIL as a text label", () => {
    render(<CheckStatusBadge status="FAIL" />);
    expect(screen.getByText("FAIL")).toBeInTheDocument();
  });

  it("renders a human label for fail-closed statuses", () => {
    render(<CheckStatusBadge status="INSUFFICIENT_EVIDENCE" />);
    expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
  });

  it("falls back to UNKNOWN for an unknown status", () => {
    render(<CheckStatusBadge status="" />);
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });
});
