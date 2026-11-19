import fs from "node:fs";
import path from "node:path";
import { EVM_CHAINS, STATE_DIR, type ChainKey, type Config } from "./config.ts";
import { bitcoinEarnings, EVM_NATIVE, evmEarnings, kaspaEarnings, SOL_NATIVE, solanaEarnings, USDC, type Earning } from "./chains/index.ts";

export interface Scan {
  demo: boolean;
  at: number;
  earnings: Earning[];
  totalUsd: number;
  newUsd: number;
  byChain: Record<string, { usd: number; newUsd: number; count: number }>;
  previousAt: number | null;
  warnings: string[];
}

const SNAPSHOT = path.join(STATE_DIR, "snapshot.json");
const key = (e: Earning) => `${e.chain}|${e.wallet}|${e.token}`;

function readSnapshot(): { at: number; amounts: Record<string, number> } | null {
  try { return JSON.parse(fs.readFileSync(SNAPSHOT, "utf8")); } catch { return null; }
}
function writeSnapshot(earnings: Earning[], at: number) {
  fs.mkdirSync(STATE_DIR, { recursive: true });
  fs.writeFileSync(SNAPSHOT, JSON.stringify({ at, amounts: Object.fromEntries(earnings.map((e) => [key(e), e.amount])) }, null, 2));
}

/** Sample mining book for demo mode: GPU rig (Kaspa), a DePIN node on Solana, staking and an L2 farm. Fixed prices, no network. */
function demoEarnings(): Earning[] {
  const w = { sol: "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", evm: "0x5a0b54d5dc17e0aadc383d2db43b0a0d3e029c4c", kas: "kaspa:qqkqkzjvr7zwxxmjxjkmxxdwju9kjs6e9u82uh59z07vgaks6gg62v8707g73", btc: "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh" };
  const e = (chain: ChainKey, wallet: string, symbol: string, amount: number, priceUsd: number, token: string, decimals: number, native: boolean, newAmount: number): Earning =>
    ({ chain, wallet, symbol, amount, priceUsd, usd: amount * priceUsd, token, decimals, native, newAmount });
  return [
    e("kaspa", w.kas, "KAS", 18400, 0.027, "native", 8, true, 1250),
    e("solana", w.sol, "GRASS", 312, 1.62, "Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs", 9, false, 50),
    e("solana", w.sol, "SOL", 1.85, 152, SOL_NATIVE, 9, true, 0.06),
    e("arbitrum", w.evm, "ETH", 0.064, 3040, EVM_NATIVE, 18, true, 0.004),
    e("base", w.evm, "ETH", 0.0061, 3040, EVM_NATIVE, 18, true, 0),
    e("polygon", w.evm, "POL", 410, 0.21, EVM_NATIVE, 18, true, 22),
    e("bitcoin", w.btc, "BTC", 0.00185, 62600, "native", 8, true, 0.00011),
    e("solana", w.sol, "USDC", 14.2, 1, USDC.solana.address, 6, false, 0),
  ];
}

export async function scanAll(cfg: Config, opts: { remember?: boolean } = {}): Promise<Scan> {
  const warnings: string[] = [];
  const at = Date.now();
  let earnings: Earning[] = [];
  let previousAt: number | null = null;

  if (cfg.demo) {
    earnings = demoEarnings();
    previousAt = at - 6 * 3600_000;
    warnings.push('DEMO MODE: sample mining wallets and fixed prices, nothing was read. Add your public addresses and switch to live.');
  } else {
    const jobs: Promise<void>[] = [];
    const add = (p: Promise<Earning[]>, label: string) => jobs.push(p.then((x) => { earnings.push(...x); }).catch((err) => { warnings.push(`${label}: ${(err as Error).message}`); }));
    for (const w of cfg.wallets.evm) for (const c of EVM_CHAINS) add(evmEarnings(c, cfg.evmChains[c], w), `${c} ${w.slice(0, 6)}…`);
    for (const w of cfg.wallets.solana)
      jobs.push(solanaEarnings(cfg.solana.rpc, w).then(({ earnings: x, unpriced }) => {
        earnings.push(...x);
        if (unpriced) warnings.push(`Solana ${w.slice(0, 4)}…: ${unpriced} token(s) without a USD price were left out.`);
      }).catch((err) => { warnings.push(`solana ${w.slice(0, 4)}…: ${(err as Error).message}`); }));
    for (const w of cfg.wallets.kaspa) add(kaspaEarnings(w), `kaspa ${w.slice(6, 12)}…`);
    for (const w of cfg.wallets.bitcoin) add(bitcoinEarnings(w), `bitcoin ${w.slice(0, 6)}…`);
    await Promise.all(jobs);
    const total = cfg.wallets.evm.length + cfg.wallets.solana.length + cfg.wallets.kaspa.length + cfg.wallets.bitcoin.length;
    if (!total) warnings.push("No mining wallets yet: add your public payout addresses in Settings.");
    const snap = readSnapshot();
    previousAt = snap?.at ?? null;
    for (const e of earnings) e.newAmount = snap ? Math.max(0, e.amount - (snap.amounts[key(e)] ?? 0)) : 0;
    if (opts.remember !== false) writeSnapshot(earnings, at);
  }

  earnings = earnings.filter((e) => e.usd >= 0.01).sort((a, b) => b.usd - a.usd);
  const byChain: Scan["byChain"] = {};
  for (const e of earnings) {
    const c = (byChain[e.chain] ||= { usd: 0, newUsd: 0, count: 0 });
    c.usd += e.usd; c.newUsd += (e.newAmount || 0) * e.priceUsd; c.count++;
  }
  const totalUsd = earnings.reduce((s, e) => s + e.usd, 0);
  const newUsd = earnings.reduce((s, e) => s + (e.newAmount || 0) * e.priceUsd, 0);
  return { demo: cfg.demo, at, earnings, totalUsd, newUsd, byChain, previousAt, warnings };
}
