import { getJson, rpc } from "../http.ts";
import { getPrices } from "../prices.ts";
import type { ChainKey, EvmChain, EvmChainKey } from "../config.ts";

/** One balance in a mining wallet. Everything in these wallets is treated as earned income. */
export interface Earning {
  chain: ChainKey;
  wallet: string;
  symbol: string;
  amount: number;
  priceUsd: number;
  usd: number;
  /** How LI.FI / a wallet addresses this asset: ERC-20 or mint address, "native" for the chain coin. */
  token: string;
  decimals: number;
  native: boolean;
  /** Increase since the previous scan (filled in by scan.ts). */
  newAmount?: number;
}

export const EVM_NATIVE = "0x0000000000000000000000000000000000000000";
export const SOL_NATIVE = "11111111111111111111111111111111";
export const USDC: Record<string, { address: string; decimals: number }> = {
  solana: { address: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", decimals: 6 },
  ethereum: { address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", decimals: 6 },
  base: { address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", decimals: 6 },
  arbitrum: { address: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", decimals: 6 },
  polygon: { address: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", decimals: 6 },
};

// ---------- EVM: native coin + listed ERC-20s
const balanceOfData = (owner: string) => "0x70a08231" + owner.toLowerCase().replace(/^0x/, "").padStart(64, "0");

export async function evmEarnings(chain: EvmChainKey, c: EvmChain, wallet: string): Promise<Earning[]> {
  const [nativeHex, ...tokenHex] = await Promise.all([
    rpc<string>(c.rpc, "eth_getBalance", [wallet, "latest"]),
    ...c.tokens.map((t) => rpc<string>(c.rpc, "eth_call", [{ to: t.address, data: balanceOfData(wallet) }, "latest"])),
  ]);
  const prices = await getPrices([c.nativePriceId, ...c.tokens.map((t) => `${chain}:${t.address}`)]);
  const out: Earning[] = [];
  const native = Number(BigInt(nativeHex)) / 1e18;
  if (native > 0) {
    const p = prices[c.nativePriceId]?.price || 0;
    out.push({ chain, wallet, symbol: c.nativeSymbol, amount: native, priceUsd: p, usd: native * p, token: EVM_NATIVE, decimals: 18, native: true });
  }
  c.tokens.forEach((t, i) => {
    const raw = tokenHex[i] && tokenHex[i] !== "0x" ? BigInt(tokenHex[i]) : 0n;
    if (raw === 0n) return;
    const amount = Number(raw) / 10 ** t.decimals;
    const p = prices[`${chain}:${t.address}`]?.price ?? (t.symbol.startsWith("USD") ? 1 : 0);
    out.push({ chain, wallet, symbol: t.symbol, amount, priceUsd: p, usd: amount * p, token: t.address, decimals: t.decimals, native: false });
  });
  return out;
}

// ---------- Solana: SOL + every priced SPL / Token-2022 token (DePIN rewards such as GRASS land here)
const TOKEN_PROGRAMS = ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"];
interface ParsedTokenAccount { account: { data: { parsed: { info: { mint: string; tokenAmount: { uiAmount: number; decimals: number } } } } } }

export async function solanaEarnings(rpcUrl: string, wallet: string): Promise<{ earnings: Earning[]; unpriced: number }> {
  const [lamports, ...lists] = await Promise.all([
    rpc<{ value: number }>(rpcUrl, "getBalance", [wallet]),
    ...TOKEN_PROGRAMS.map((programId) => rpc<{ value: ParsedTokenAccount[] }>(rpcUrl, "getTokenAccountsByOwner", [wallet, { programId }, { encoding: "jsonParsed" }])),
  ]);
  const bal = new Map<string, { amount: number; decimals: number }>();
  for (const l of lists)
    for (const a of l.value) {
      const { mint, tokenAmount } = a.account.data.parsed.info;
      if (!tokenAmount.uiAmount) continue;
      const prev = bal.get(mint);
      bal.set(mint, { amount: (prev?.amount || 0) + tokenAmount.uiAmount, decimals: tokenAmount.decimals });
    }
  const prices = await getPrices(["coingecko:solana", ...[...bal.keys()].map((m) => `solana:${m}`)]);
  const earnings: Earning[] = [];
  let unpriced = 0;
  const sol = lamports.value / 1e9;
  if (sol > 0) {
    const p = prices["coingecko:solana"]?.price || 0;
    earnings.push({ chain: "solana", wallet, symbol: "SOL", amount: sol, priceUsd: p, usd: sol * p, token: SOL_NATIVE, decimals: 9, native: true });
  }
  for (const [mint, b] of bal) {
    const p = prices[`solana:${mint}`];
    if (!p) { unpriced++; continue; }
    earnings.push({ chain: "solana", wallet, symbol: (p.symbol || mint.slice(0, 6)).toUpperCase(), amount: b.amount, priceUsd: p.price, usd: b.amount * p.price, token: mint, decimals: b.decimals, native: false });
  }
  return { earnings, unpriced };
}

// ---------- Kaspa (PoW): api.kaspa.org, balance in sompi
export async function kaspaEarnings(wallet: string): Promise<Earning[]> {
  const r = await getJson<{ balance: number }>(`https://api.kaspa.org/addresses/${encodeURIComponent(wallet)}/balance`);
  const amount = r.balance / 1e8;
  if (!amount) return [];
  const p = (await getPrices(["coingecko:kaspa"]))["coingecko:kaspa"]?.price || 0;
  return [{ chain: "kaspa", wallet, symbol: "KAS", amount, priceUsd: p, usd: amount * p, token: "native", decimals: 8, native: true }];
}

// ---------- Bitcoin (PoW pool payouts): Esplora API, Blockstream first, mempool.space as fallback
export async function bitcoinEarnings(wallet: string): Promise<Earning[]> {
  type Esplora = { chain_stats: { funded_txo_sum: number; spent_txo_sum: number }; mempool_stats: { funded_txo_sum: number; spent_txo_sum: number } };
  let r: Esplora;
  try {
    r = await getJson<Esplora>(`https://blockstream.info/api/address/${wallet}`);
  } catch {
    r = await getJson<Esplora>(`https://mempool.space/api/address/${wallet}`, { headers: { "user-agent": "nyro-agent" } });
  }
  const sats = r.chain_stats.funded_txo_sum - r.chain_stats.spent_txo_sum + r.mempool_stats.funded_txo_sum - r.mempool_stats.spent_txo_sum;
  const amount = sats / 1e8;
  if (amount <= 0) return [];
  const p = (await getPrices(["coingecko:bitcoin"]))["coingecko:bitcoin"]?.price || 0;
  return [{ chain: "bitcoin", wallet, symbol: "BTC", amount, priceUsd: p, usd: amount * p, token: "native", decimals: 8, native: true }];
}
