import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerdictBadge } from "./VerdictBadge";

describe("VerdictBadge", () => {
  it("renders the VERIFIED label with a check mark", () => {
    render(<VerdictBadge verdict="VERIFIED" />);
    expect(screen.getByText("VERIFIED")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
  });

  it("renders the REJECTED label with a cross", () => {
    render(<VerdictBadge verdict="REJECTED" />);
    expect(screen.getByText("REJECTED")).toBeInTheDocument();
    expect(screen.getByText("✕")).toBeInTheDocument();
  });

  it("renders the INCONCLUSIVE label with a question mark", () => {
    render(<VerdictBadge verdict="INCONCLUSIVE" />);
    expect(screen.getByText("INCONCLUSIVE")).toBeInTheDocument();
  });

  it("renders PENDING and RUNNING as neutral statuses", () => {
    render(<VerdictBadge verdict="PENDING" />);
    expect(screen.getByText("PENDING")).toBeInTheDocument();
  });

  it("falls back to UNKNOWN for an empty verdict", () => {
    render(<VerdictBadge verdict="" />);
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });

  it("still shows a text label for an unexpected verdict", () => {
    render(<VerdictBadge verdict="SOMETHING_ELSE" />);
    expect(screen.getByText("SOMETHING_ELSE")).toBeInTheDocument();
  });
});
