"use client";

import { useState, type ReactNode } from "react";
import { NETWORK_NAME } from "@/lib/config";
import { truncateMiddle } from "@/lib/format";
import { useWallet } from "@/lib/wallet-context";

export function WalletButton() {
  const {
    detected,
    available,
    address,
    chainIdHex,
    isCorrectNetwork,
    connecting,
    error,
    connect,
    disconnect,
    switchToStudionet,
    clearError,
  } = useWallet();
  const [menuOpen, setMenuOpen] = useState(false);
  const [hintOpen, setHintOpen] = useState(false);

  let control: ReactNode;

  if (!detected) {
    // Server render + first paint: keep stable markup to avoid hydration drift.
    control = (
      <button type="button" className="btn btn-secondary" disabled>
        Connect Wallet
      </button>
    );
  } else if (!available) {
    control = (
      <div className="relative">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setHintOpen((v) => !v)}
          aria-expanded={hintOpen}
        >
          Connect Wallet
        </button>
        {hintOpen ? (
          <div className="card card-pad absolute right-0 z-50 mt-2 w-72">
            <p className="text-sm font-semibold">No wallet detected</p>
            <p className="mt-1 text-xs text-muted">
              Install an EIP-1193 browser wallet such as MetaMask, then reload
              this page. Your wallet — never this app — holds the keys.
            </p>
            <button
              type="button"
              className="btn btn-ghost mt-3"
              onClick={() => setHintOpen(false)}
            >
              Dismiss
            </button>
          </div>
        ) : null}
      </div>
    );
  } else if (!address) {
    control = (
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => void connect()}
        disabled={connecting}
      >
        {connecting ? "Connecting…" : "Connect Wallet"}
      </button>
    );
  } else {
    control = (
      <div className="flex items-center gap-2">
        {!isCorrectNetwork ? (
          <button
            type="button"
            className="btn btn-secondary"
            style={{
              borderColor: "rgba(251, 191, 36, 0.5)",
              color: "var(--color-inconclusive)",
            }}
            onClick={() => void switchToStudionet()}
          >
            Switch to {NETWORK_NAME}
          </button>
        ) : null}
        <div className="relative">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
          >
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 rounded-full"
              style={{
                backgroundColor: isCorrectNetwork
                  ? "var(--color-verified)"
                  : "var(--color-inconclusive)",
              }}
            />
            <span className="mono">{truncateMiddle(address, 6, 4)}</span>
          </button>
          {menuOpen ? (
            <div
              role="menu"
              className="card card-pad absolute right-0 z-50 mt-2 w-72"
            >
              <p className="text-xs tracking-wide text-muted uppercase">
                Connected account
              </p>
              <p className="mono mt-1 break-all">{address}</p>
              <p className="mt-3 text-xs tracking-wide text-muted uppercase">
                Network
              </p>
              <p
                className="mt-1 text-sm"
                style={{
                  color: isCorrectNetwork
                    ? "var(--color-verified)"
                    : "var(--color-inconclusive)",
                }}
              >
                {isCorrectNetwork
                  ? NETWORK_NAME
                  : chainIdHex
                    ? `Wrong network (chain ${chainIdHex})`
                    : "Unknown network"}
              </p>
              <button
                type="button"
                className="btn btn-ghost mt-3 w-full"
                onClick={() => {
                  disconnect();
                  setMenuOpen(false);
                }}
              >
                Disconnect
              </button>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <>
      {control}
      {error ? (
        <div
          role="alert"
          className="card card-pad fixed right-4 bottom-4 z-50 w-80"
          style={{ borderColor: "rgba(248, 113, 113, 0.5)" }}
        >
          <p className="text-sm" style={{ color: "var(--color-rejected)" }}>
            {error}
          </p>
          <button
            type="button"
            className="btn btn-ghost mt-2"
            onClick={clearError}
          >
            Dismiss
          </button>
        </div>
      ) : null}
    </>
  );
}
