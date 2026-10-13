import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorCard } from "./ErrorCard";

describe("ErrorCard", () => {
  it("announces itself as an alert with the title and detail", () => {
    render(
      <ErrorCard
        title="Could not reach the network"
        detail="The read against GenLayer Studionet did not complete."
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Could not reach the network" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/did not complete/)).toBeInTheDocument();
  });

  it("renders an optional action when provided", () => {
    render(
      <ErrorCard
        title="No such verification"
        detail="Check the id and try again."
        action={<button type="button">Retry</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
