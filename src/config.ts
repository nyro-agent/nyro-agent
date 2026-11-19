import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Package root (holds config.example.json and web/). Works from src/ (dev) and dist/ (published). */
export const PKG_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
/** Where your settings live. Outside the package, so npx/npm updates never touch them. */
export const HOME_DIR = process.env.NYRO_HOME || path.join(os.homedir(), ".nyro");
const CONFIG_PATH = process.env.NYRO_CONFIG || path.join(HOME_DIR, "config.json");
const EXAMPLE_PATH = path.join(PKG_ROOT, "config.example.json");
export const STATE_DIR = path.join(HOME_DIR, "state");

export const EVM_CHAINS = ["ethereum", "base", "arbitrum", "polygon"] as const;
export type EvmChainKey = (typeof EVM_CHAINS)[number];
export type ChainKey = EvmChainKey | "solana" | "kaspa" | "bitcoin";
/** Chains USDC can be consolidated on (LI.FI routes to these). */
export const PAYOUT_CHAINS = ["solana", "ethereum", "base", "arbitrum", "polygon"] as const;
export type PayoutChain = (typeof PAYOUT_CHAINS)[number];

export interface EvmToken { symbol: string; address: string; decimals: number }
export interface EvmChain { rpc: string; nativeSymbol: string; nativePriceId: string; tokens: EvmToken[] }

export interface Config {
  /** Public addresses only. Every balance in these wallets is treated as mining / staking / node income. */
  wallets: { evm: string[]; solana: string[]; kaspa: string[]; bitcoin: string[] };
  solana: { rpc: string };
  evmChains: Record<EvmChainKey, EvmChain>;
  payout: {
    /** Chain where everything is consolidated into USDC. */
    chain: PayoutChain;
    /** Your own wallet on that chain that receives the USDC (defaults to your first wallet of that family). */
    collectWallet: string;
    /** Deposit addresses copied from your Robinhood app, per asset. Optional. */
    robinhood: { USDC: string; BTC: string };
  };
  rules: {
    /** Skip anything worth less than this. */
    minHarvestUsd: number;
    /** Hold a token when the route costs more than this share of its value (gas + bridge + swap). */
    maxCostPct: number;
    slippagePct: number;
    /** Leave this much of each chain's native coin behind for future gas. */
    keepGasUsd: number;
  };
  /** How to split the consolidated USDC once it is in Robinhood (you place these orders yourself). */
  allocation: { symbol: string; pct: number }[];
  demo: boolean;
}

export const configPath = () => CONFIG_PATH;

/** Your config if it exists, otherwise the bundled example (demo mode). */
export function loadConfig(): Config {
  const file = fs.existsSync(CONFIG_PATH) ? CONFIG_PATH : EXAMPLE_PATH;
  const cfg = JSON.parse(fs.readFileSync(file, "utf8")) as Config;
  if (process.env.NYRO_DEMO === "1") cfg.demo = true;
  return cfg;
}

export function saveConfig(cfg: Config) {
  fs.mkdirSync(path.dirname(CONFIG_PATH), { recursive: true });
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2) + "\n");
}

export function ensureConfigFile(): string {
  if (!fs.existsSync(CONFIG_PATH)) {
    fs.mkdirSync(path.dirname(CONFIG_PATH), { recursive: true });
    fs.copyFileSync(EXAMPLE_PATH, CONFIG_PATH);
  }
  return CONFIG_PATH;
}

// ---------- address checks (public addresses only; anything that looks like a secret is refused)
const ADDR = {
  evm: /^0x[0-9a-fA-F]{40}$/,
  solana: /^[1-9A-HJ-NP-Za-km-z]{32,44}$/,
  kaspa: /^kaspa:[a-z0-9]{61,63}$/,
  bitcoin: /^(bc1[02-9ac-hj-np-z]{11,71}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$/,
};
export type WalletFamily = keyof typeof ADDR;
export const LOOKS_SECRET = (s: string) => /\s/.test(s.trim()) || /^(0x)?[0-9a-fA-F]{64}$/.test(s.trim()) || /^[1-9A-HJ-NP-Za-km-z]{80,90}$/.test(s.trim());

export function checkAddress(family: WalletFamily, value: string): string | null {
  const a = value.trim();
  if (LOOKS_SECRET(a)) return "That looks like a private key or seed phrase. Only paste PUBLIC addresses, and never share your keys.";
  if (!ADDR[family].test(a)) return `Not a valid ${family} address: ${a}`;
  return null;
}

/** Which wallet family a payout chain uses. */
export const familyOf = (c: PayoutChain): WalletFamily => (c === "solana" ? "solana" : "evm");

export function validateRules(r: Config["rules"]): string | null {
  if (!(r.minHarvestUsd >= 0 && r.minHarvestUsd <= 100_000)) return "Minimum harvest must be between $0 and $100,000.";
  if (!(r.maxCostPct > 0 && r.maxCostPct <= 50)) return "Max cost must be between 0 and 50%.";
  if (!(r.slippagePct >= 0.05 && r.slippagePct <= 5)) return "Slippage must be between 0.05% and 5%.";
  if (!(r.keepGasUsd >= 0 && r.keepGasUsd <= 1000)) return "Gas reserve must be between $0 and $1,000.";
  return null;
}

export function validateAllocation(a: Config["allocation"]): string | null {
  if (!Array.isArray(a) || a.length > 10) return "Up to 10 allocation lines.";
  for (const x of a) {
    if (!/^[A-Z0-9.]{1,10}$/.test(String(x.symbol))) return `"${x.symbol}" is not a ticker.`;
    if (!(x.pct > 0 && x.pct <= 100)) return `${x.symbol}: percent must be above 0.`;
  }
  const sum = a.reduce((s, x) => s + x.pct, 0);
  if (a.length && Math.abs(sum - 100) > 0.01) return `Allocation must add up to 100 (got ${sum}).`;
  return null;
}
