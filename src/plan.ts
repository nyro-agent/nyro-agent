import crypto from "node:crypto";
import { getJson } from "./http.ts";
import { familyOf, type Config, type PayoutChain } from "./config.ts";
import { USDC, type Earning } from "./chains/index.ts";
import type { Scan } from "./scan.ts";

/** LI.FI chain ids. Kaspa is not bridgeable today; Bitcoin goes straight to an address that accepts BTC. */
const LIFI_CHAIN: Record<string, number> = { ethereum: 1, base: 8453, arbitrum: 42161, polygon: 137, solana: 1151111081099710 };

export type LegMode = "wallet-sign" | "manual" | "robinhood";
export type Decision = "harvest" | "hold";

export interface Leg {
  id: number;
  step: "route" | "deposit" | "allocate";
  mode: LegMode;
  chain: string;
  detail: string;
  usd: number;
  decision?: Decision;
  reason?: string;
  costUsd?: number;
  costPct?: number;
  tool?: string;
  etaSec?: number;
  /** Unsigned transaction from LI.FI, for your wallet to sign. Nyro never signs. */
  tx?: Record<string, unknown>;
  estimated?: boolean;
}

export interface Plan {
  id: string;
  createdAt: number;
  demo: boolean;
  payout: PayoutChain;
  grossUsd: number;
  harvestUsd: number;
  costUsd: number;
  netUsd: number;
  heldUsd: number;
  legs: Leg[];
  notes: string[];
}

const plans = new Map<string, Plan>();
export const PLAN_TTL_MS = 10 * 60_000; // quotes go stale fast
export const getPlan = (id: string) => plans.get(id);

interface LifiQuote {
  estimate: { fromAmountUSD?: string; toAmountUSD?: string; toAmount: string; feeCosts?: { amountUSD?: string }[]; gasCosts?: { amountUSD?: string }[]; executionDuration?: number };
  toolDetails?: { name?: string };
  transactionRequest?: Record<string, unknown>;
}

async function lifiQuote(e: Earning, rawAmount: bigint, to: PayoutChain, toAddress: string, slippagePct: number): Promise<LifiQuote> {
  const q = new URLSearchParams({
    fromChain: String(LIFI_CHAIN[e.chain]), toChain: String(LIFI_CHAIN[to]),
    fromToken: e.token, toToken: USDC[to].address,
    fromAddress: e.wallet, toAddress, fromAmount: rawAmount.toString(),
    slippage: String(slippagePct / 100), integrator: "nyro-agent",
  });
  return getJson<LifiQuote>(`https://li.quest/v1/quote?${q}`, {}, 20_000);
}

const usd = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const amt = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 6 });

/** Demo stand-in for a LI.FI quote: typical L2 / mainnet costs, clearly marked as estimates. */
function demoCost(e: Earning, value: number, to: PayoutChain) {
  const gas: Record<string, number> = { ethereum: 2.4, base: 0.01, arbitrum: 0.02, polygon: 0.01, solana: 0.002 };
  const cross = e.chain !== to;
  const costUsd = value * (cross ? 0.0035 : 0.0015) + (gas[e.chain] ?? 0.05);
  return { costUsd, tool: cross ? "Across (est.)" : "Jupiter (est.)", etaSec: cross ? 40 : 5 };
}

export async function buildPlan(scan: Scan, cfg: Config): Promise<Plan> {
  const r = cfg.rules;
  const to = cfg.payout.chain;
  const collect = cfg.payout.collectWallet || (familyOf(to) === "solana" ? cfg.wallets.solana[0] : cfg.wallets.evm[0]) || (scan.demo ? (to === "solana" ? "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" : "0x5a0b54d5dc17e0aadc383d2db43b0a0d3e029c4c") : "");
  const legs: Leg[] = [];
  const notes: string[] = [];
  const add = (l: Omit<Leg, "id">) => legs.push({ ...l, id: legs.length + 1 });
  let harvestUsd = 0, costUsd = 0, heldUsd = 0, alreadyUsdc = 0;

  for (const e of scan.earnings) {
    const isPayoutUsdc = e.chain === to && e.token.toLowerCase() === USDC[to].address.toLowerCase();
    if (isPayoutUsdc) { alreadyUsdc += e.usd; continue; }

    // keep a little native coin behind so the wallet can still pay gas
    const reserve = e.native && LIFI_CHAIN[e.chain] ? Math.min(e.usd, r.keepGasUsd) : 0;
    const value = e.usd - reserve;
    const hold = (reason: string) => { heldUsd += e.usd; add({ step: "route", mode: "manual", chain: e.chain, detail: `Hold ${amt(e.amount)} ${e.symbol} on ${e.chain}`, usd: e.usd, decision: "hold", reason }); };

    if (value < r.minHarvestUsd) { hold(`${usd(value)} is under your ${usd(r.minHarvestUsd)} minimum${reserve ? ` (after keeping ${usd(reserve)} for gas)` : ""}.`); continue; }

    if (e.chain === "bitcoin") {
      if (cfg.payout.robinhood.BTC) {
        harvestUsd += value;
        add({ step: "deposit", mode: "wallet-sign", chain: "bitcoin", detail: `Send ${amt(e.amount)} BTC from ${e.wallet.slice(0, 8)}… to your Robinhood BTC deposit address`, usd: value, decision: "harvest", reason: "Robinhood takes BTC directly, no swap needed." });
      } else hold("Add your Robinhood BTC deposit address in Settings to send BTC straight there.");
      continue;
    }
    if (e.chain === "kaspa") {
      heldUsd += e.usd;
      add({ step: "route", mode: "manual", chain: "kaspa", detail: `Sell ${amt(e.amount)} KAS for USDC on an exchange that lists Kaspa, then withdraw USDC to ${to}`, usd: e.usd, decision: "hold", reason: "No bridge or DEX route for Kaspa exists in LI.FI, so this step is manual." });
      continue;
    }
    if (!collect) { hold(`Add a ${familyOf(to)} wallet to receive USDC on ${to}.`); continue; }

    const fraction = value / e.usd;
    const raw = BigInt(Math.floor(e.amount * fraction * 10 ** Math.min(e.decimals, 18)));
    let cost: number, tool: string | undefined, etaSec: number | undefined, tx: Record<string, unknown> | undefined, estimated = false;
    if (scan.demo) {
      ({ costUsd: cost, tool, etaSec } = demoCost(e, value, to));
      estimated = true;
    } else {
      try {
        const q = await lifiQuote(e, raw, to, collect, r.slippagePct);
        // The output is USDC, so count what actually arrives (toAmount) instead of LI.FI's USD estimate of it, which
        // can price the output above the input. Never report less than the fees LI.FI itemises, then add gas.
        const fromUsd = Number(q.estimate.fromAmountUSD ?? value);
        const arrives = Number(q.estimate.toAmount) / 10 ** USDC[to].decimals;
        const fees = (q.estimate.feeCosts || []).reduce((s, f) => s + Number(f.amountUSD || 0), 0);
        const gas = (q.estimate.gasCosts || []).reduce((s, g) => s + Number(g.amountUSD || 0), 0);
        cost = Math.max(fromUsd - arrives, fees, 0) + gas;
        tool = q.toolDetails?.name;
        etaSec = q.estimate.executionDuration;
        tx = q.transactionRequest;
      } catch (err) {
        hold(`No route right now (${(err as Error).message.slice(0, 120)}). Try again later.`);
        continue;
      }
    }
    const pct = (cost / value) * 100;
    if (pct > r.maxCostPct) {
      heldUsd += e.usd;
      add({ step: "route", mode: "manual", chain: e.chain, detail: `Hold ${amt(e.amount)} ${e.symbol} on ${e.chain}`, usd: e.usd, decision: "hold", costUsd: cost, costPct: pct, tool, estimated, reason: `Moving it costs ${usd(cost)} (${pct.toFixed(1)}%), above your ${r.maxCostPct}% limit. Wait for more to accumulate or for cheaper gas.` });
      continue;
    }
    harvestUsd += value; costUsd += cost;
    const cross = e.chain !== to;
    add({
      step: "route", mode: "wallet-sign", chain: e.chain, usd: value, decision: "harvest", costUsd: cost, costPct: pct, tool, etaSec, tx, estimated,
      detail: `${cross ? "Bridge + swap" : "Swap"} ${amt(e.amount * fraction)} ${e.symbol} on ${e.chain} → USDC on ${to}`,
      reason: `${usd(cost)} total cost (${pct.toFixed(2)}%)${tool ? ` via ${tool}` : ""}.`,
    });
  }

  const netUsdc = harvestUsd - costUsd - legs.filter((l) => l.step === "deposit").reduce((s, l) => s + l.usd, 0) + alreadyUsdc;
  if (netUsdc >= r.minHarvestUsd) {
    if (cfg.payout.robinhood.USDC)
      add({ step: "deposit", mode: "wallet-sign", chain: to, usd: netUsdc, detail: `Send ~${usd(netUsdc)} USDC on ${to} from ${collect.slice(0, 6)}… to your Robinhood USDC deposit address`, reason: "Check in the Robinhood app that it accepts USDC on this network before sending." });
    else notes.push(`Add your Robinhood USDC deposit address (and check which network Robinhood accepts) to finish the route. Until then the USDC stays in ${collect.slice(0, 6)}… on ${to}.`);
  }
  const intoRobinhood = (cfg.payout.robinhood.USDC ? netUsdc : 0) + legs.filter((l) => l.step === "deposit" && l.chain === "bitcoin").reduce((s, l) => s + l.usd, 0);
  if (intoRobinhood > 0 && cfg.allocation.length)
    for (const a of cfg.allocation)
      add({ step: "allocate", mode: "robinhood", chain: "robinhood", usd: (intoRobinhood * a.pct) / 100, detail: `Buy ${usd((intoRobinhood * a.pct) / 100)} of ${a.symbol} in the Robinhood app (${a.pct}%)`, reason: "Placed by you in Robinhood. Nyro has no access to your brokerage." });

  if (legs.some((l) => l.mode === "wallet-sign")) notes.push("Every on-chain step is a transaction you sign in your own wallet. Nyro never holds keys and never sends anything.");
  if (scan.demo) notes.push("DEMO: costs are typical estimates, not live quotes.");
  if (alreadyUsdc) notes.push(`${usd(alreadyUsdc)} is already USDC on ${to}.`);

  const plan: Plan = {
    id: crypto.randomUUID().slice(0, 8), createdAt: Date.now(), demo: scan.demo, payout: to,
    grossUsd: scan.totalUsd, harvestUsd, costUsd, netUsd: harvestUsd - costUsd + alreadyUsdc, heldUsd, legs, notes,
  };
  plans.set(plan.id, plan);
  return plan;
}

