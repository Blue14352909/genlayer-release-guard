"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { CHAIN_ID_HEX, NETWORK_NAME } from "./config";
import {
  addChainParams,
  firstAddress,
  getInjectedProvider,
  providerErrorCode,
  UNKNOWN_CHAIN_CODE,
  type EIP1193Provider,
} from "./wallet";

interface WalletContextValue {
  provider: EIP1193Provider | null;
  /** False until we have checked for an injected provider on the client. */
  detected: boolean;
  available: boolean;
  address: string | null;
  chainIdHex: string | null;
  isCorrectNetwork: boolean;
  connecting: boolean;
  error: string | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  switchToStudionet: () => Promise<void>;
  clearError: () => void;
}

const WalletContext = createContext<WalletContextValue | null>(null);

/**
 * The injected provider is external, mutable browser state, so it is read with
 * `useSyncExternalStore` instead of being copied into state from an effect.
 * The server snapshot (and the hydration render) is always `null`, which keeps
 * the first paint identical to the server markup.
 */
function subscribeToProvider(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  // MetaMask (and friends) dispatch this when they inject late.
  window.addEventListener("ethereum#initialized", onChange);
  return () => window.removeEventListener("ethereum#initialized", onChange);
}

function getProviderSnapshot(): EIP1193Provider | null {
  return getInjectedProvider();
}

function getServerProviderSnapshot(): EIP1193Provider | null {
  return null;
}

function subscribeToNothing(): () => void {
  return () => {};
}

/** False until hydration completes, so server and first client paint match. */
function getDetectedSnapshot(): boolean {
  return true;
}

function getServerDetectedSnapshot(): boolean {
  return false;
}

export function WalletProvider({ children }: { children: ReactNode }) {
  const provider = useSyncExternalStore(
    subscribeToProvider,
    getProviderSnapshot,
    getServerProviderSnapshot,
  );
  const detected = useSyncExternalStore(
    subscribeToNothing,
    getDetectedSnapshot,
    getServerDetectedSnapshot,
  );
  const [address, setAddress] = useState<string | null>(null);
  const [chainIdHex, setChainIdHex] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const readChain = useCallback(async (p: EIP1193Provider) => {
    try {
      const id = await p.request({ method: "eth_chainId" });
      setChainIdHex(typeof id === "string" ? id : null);
    } catch {
      setChainIdHex(null);
    }
  }, []);

  // Restore an existing (non-prompting) connection. eth_accounts never opens a
  // wallet popup; only an explicit Connect click requests accounts.
  useEffect(() => {
    if (!provider) return;

    let cancelled = false;
    (async () => {
      try {
        const accounts = await provider.request({ method: "eth_accounts" });
        if (cancelled) return;
        const addr = firstAddress(accounts);
        if (addr) {
          setAddress(addr);
          void readChain(provider);
        }
      } catch {
        /* no existing connection — user must click Connect */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [provider, readChain]);

  // Keep state in sync with the wallet.
  useEffect(() => {
    if (!provider) return;
    const onAccounts = (...args: unknown[]) => {
      setAddress(firstAddress(args[0]));
    };
    const onChain = (...args: unknown[]) => {
      setChainIdHex(typeof args[0] === "string" ? (args[0] as string) : null);
    };
    provider.on?.("accountsChanged", onAccounts);
    provider.on?.("chainChanged", onChain);
    return () => {
      provider.removeListener?.("accountsChanged", onAccounts);
      provider.removeListener?.("chainChanged", onChain);
    };
  }, [provider]);

  const connect = useCallback(async () => {
    setError(null);
    const p = getInjectedProvider();
    if (!p) {
      setError(
        "No EIP-1193 wallet detected. Install MetaMask (or a compatible wallet) and reload.",
      );
      return;
    }
    setConnecting(true);
    try {
      const accounts = await p.request({ method: "eth_requestAccounts" });
      const addr = firstAddress(accounts);
      if (!addr) {
        setError("The wallet did not return an account.");
        return;
      }
      setAddress(addr);
      await readChain(p);
    } catch (err) {
      setError(
        providerErrorCode(err) === 4001
          ? "Connection request was rejected in your wallet."
          : "Could not connect to the wallet.",
      );
    } finally {
      setConnecting(false);
    }
  }, [readChain]);

  const disconnect = useCallback(() => {
    // The browser wallet owns the connection; this only resets local UI state.
    setAddress(null);
    setChainIdHex(null);
    setError(null);
  }, []);

  const switchToStudionet = useCallback(async () => {
    setError(null);
    const p = provider ?? getInjectedProvider();
    if (!p) {
      setError("No wallet available to switch networks.");
      return;
    }
    try {
      await p.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: CHAIN_ID_HEX }],
      });
    } catch (err) {
      if (providerErrorCode(err) === UNKNOWN_CHAIN_CODE) {
        try {
          await p.request({
            method: "wallet_addEthereumChain",
            params: [addChainParams()],
          });
        } catch {
          setError(`Could not add ${NETWORK_NAME} to your wallet.`);
          return;
        }
      } else if (providerErrorCode(err) === 4001) {
        setError("Network switch was rejected in your wallet.");
        return;
      } else {
        setError(`Could not switch to ${NETWORK_NAME}.`);
        return;
      }
    }
    await readChain(p);
  }, [provider, readChain]);

  const value = useMemo<WalletContextValue>(
    () => ({
      provider,
      detected,
      available: Boolean(provider),
      address,
      chainIdHex,
      isCorrectNetwork: chainIdHex === CHAIN_ID_HEX,
      connecting,
      error,
      connect,
      disconnect,
      switchToStudionet,
      clearError: () => setError(null),
    }),
    [
      provider,
      detected,
      address,
      chainIdHex,
      connecting,
      error,
      connect,
      disconnect,
      switchToStudionet,
    ],
  );

  return (
    <WalletContext.Provider value={value}>{children}</WalletContext.Provider>
  );
}

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext);
  if (!ctx) {
    throw new Error("useWallet must be used inside a WalletProvider");
  }
  return ctx;
}
