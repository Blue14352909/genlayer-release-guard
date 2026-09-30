import { CHAIN, CHAIN_ID_HEX, EXPLORER_BASE } from "./config";

/**
 * Minimal EIP-1193 provider surface. This is the injected browser wallet
 * interface (MetaMask and compatible wallets). We never read private keys or
 * create accounts — signing always happens inside the user's wallet.
 */
export interface EIP1193Provider {
  request(args: {
    method: string;
    params?: readonly unknown[] | Record<string, unknown>;
  }): Promise<unknown>;
  on?(event: string, handler: (...args: unknown[]) => void): void;
  removeListener?(event: string, handler: (...args: unknown[]) => void): void;
  isMetaMask?: boolean;
}

declare global {
  interface Window {
    ethereum?: EIP1193Provider;
  }
}

export function getInjectedProvider(): EIP1193Provider | null {
  if (typeof window === "undefined") return null;
  return window.ethereum ?? null;
}

/** EIP-1193 wallet error shape (used to detect rejects and unknown chains). */
export interface ProviderRpcError extends Error {
  code?: number;
}

export function providerErrorCode(error: unknown): number | undefined {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code?: unknown }).code;
    if (typeof code === "number") return code;
  }
  return undefined;
}

export const USER_REJECTED_CODE = 4001;
export const UNKNOWN_CHAIN_CODE = 4902;

/** Parameters passed to wallet_addEthereumChain, derived from the SDK chain. */
export function addChainParams() {
  return {
    chainId: CHAIN_ID_HEX,
    chainName: CHAIN.name,
    nativeCurrency: CHAIN.nativeCurrency,
    rpcUrls: [...CHAIN.rpcUrls.default.http],
    blockExplorerUrls: [EXPLORER_BASE],
  };
}

/** Addresses returned by eth_accounts / eth_requestAccounts. */
export function firstAddress(result: unknown): string | null {
  if (Array.isArray(result) && typeof result[0] === "string") {
    return result[0];
  }
  return null;
}
