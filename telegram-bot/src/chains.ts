/**
 * Chain configuration for the FCFS auto-minter.
 *
 * SeaDrop 1.0 was deployed by ProjectOpenSea via deterministic CREATE2 to
 * the same address on most EVM chains. The defaults below match the
 * canonical address; you can override via env vars per chain if a
 * collection uses a custom drop contract.
 *
 * Sources:
 *   https://github.com/ProjectOpenSea/seadrop
 *   https://etherscan.io/address/0x00005EA00Ac477B1030CE78506496e8C2dE24bf5
 *   https://basescan.org/address/0x00005EA00Ac477B1030CE78506496e8C2dE24bf5
 */
export interface ChainConfig {
  key: "eth" | "base";
  name: string;
  chainId: number;
  rpcEnvVar: string;
  seaDropEnvVar: string;
  defaultSeaDrop: string;
  blockExplorer: string;
}

const CANONICAL_SEADROP = "0x00005EA00Ac477B1030CE78506496e8C2dE24bf5";

export const CHAINS: Record<string, ChainConfig> = {
  eth: {
    key: "eth",
    name: "Ethereum",
    chainId: 1,
    rpcEnvVar: "ETH_RPC_URL",
    seaDropEnvVar: "ETH_SEADROP_ADDRESS",
    defaultSeaDrop: CANONICAL_SEADROP,
    blockExplorer: "https://etherscan.io",
  },
  base: {
    key: "base",
    name: "Base",
    chainId: 8453,
    rpcEnvVar: "BASE_RPC_URL",
    seaDropEnvVar: "BASE_SEADROP_ADDRESS",
    defaultSeaDrop: CANONICAL_SEADROP,
    blockExplorer: "https://basescan.org",
  },
};

export function getChain(key: string): ChainConfig {
  const cfg = CHAINS[key as keyof typeof CHAINS];
  if (!cfg) {
    const known = Object.keys(CHAINS).join(", ");
    throw new Error(`Unknown chain "${key}". Known: ${known}`);
  }
  return cfg;
}

export function getSeaDropAddress(cfg: ChainConfig): string {
  return process.env[cfg.seaDropEnvVar]?.trim() || cfg.defaultSeaDrop;
}

export function getRpcUrl(cfg: ChainConfig): string {
  const url = process.env[cfg.rpcEnvVar]?.trim();
  if (!url) {
    throw new Error(
      `Missing RPC URL for ${cfg.name}: set env ${cfg.rpcEnvVar}`,
    );
  }
  return url;
}
