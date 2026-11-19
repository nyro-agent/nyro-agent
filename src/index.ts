/**
 * NYRO: an AI mining agent. It reads your mining / staking / node payout wallets on every chain, shows what came in,
 * checks what it costs to consolidate each token into USDC (live LI.FI quotes), and plans the route to your Robinhood
 * deposit address plus how to split it there.
 *
 * Safety model:
 *  - public addresses only, never private keys; every on-chain step is an unsigned transaction you sign yourself
 *  - tokens are held, not moved, when the route costs more than your limit or the value is under your minimum
 *  - Robinhood orders are instructions for you; Nyro has no access to your brokerage
 *
 * Usage:
 *   npx -y nyro-agent          MCP server on stdio
 *   npx -y nyro-agent init     create ~/.nyro/config.json
 *   npx -y nyro-agent web      web app (dashboard, harvest plan, terminal, settings) on http://127.0.0.1:5550
 */
import fs from "node:fs";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { configPath, ensureConfigFile, loadConfig, saveConfig, validateAllocation, validateRules } from "./config.ts";
import { scanAll } from "./scan.ts";
import { buildPlan, getPlan, PLAN_TTL_MS, type Plan } from "./plan.ts";

const VERSION = "0.1.0";
const cmd = process.argv[2];
const arg = (name: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
};

if (cmd === "--version" || cmd === "-v") {
  console.log(VERSION);
  process.exit(0);
}
if (cmd === "--help" || cmd === "-h") {
  console.log(`nyro-agent ${VERSION}

  npx -y nyro-agent          start the MCP server (stdio)
  npx -y nyro-agent init     create ${configPath()}
  npx -y nyro-agent web      web app on http://127.0.0.1:5550 (--port N, --host H)

MCP client config:
  { "mcpServers": { "nyro": { "command": "npx", "args": ["-y", "nyro-agent"] } } }`);
  process.exit(0);
}

const usd = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const amt = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 6 });

function renderPlan(p: Plan) {
  const mode = { "wallet-sign": "you sign in wallet", manual: "manual", robinhood: "you, in Robinhood" } as const;
  return [
    `Plan ${p.id}${p.demo ? " (DEMO)" : ""} · payout USDC on ${p.payout} · valid ${PLAN_TTL_MS / 60000} min`,
    `Harvest ${usd(p.harvestUsd)} · route cost ${usd(p.costUsd)} · arrives ~${usd(p.netUsd)} · held ${usd(p.heldUsd)}`,
    "",
    "| # | Step | Chain | Action | Value | Cost | Who | Why |",
    "|---|---|---|---|---|---|---|---|",
    ...p.legs.map((l) => `| ${l.id} | ${l.decision === "hold" ? "HOLD" : l.step} | ${l.chain} | ${l.detail} | ${usd(l.usd)} | ${l.costUsd !== undefined ? `${usd(l.costUsd)} (${(l.costPct ?? 0).toFixed(2)}%)${l.estimated ? " est." : ""}` : "–"} | ${mode[l.mode]} | ${l.reason ?? ""} |`),
    "",
    ...p.notes,
  ].join("\n");
}

if (cmd === "init") {
  const existed = fs.existsSync(configPath());
  console.log(`${existed ? "Config already exists" : "Created"}: ${ensureConfigFile()}

Next: add your public payout addresses, your Robinhood deposit addresses and set "demo": false,
or run  npx -y nyro-agent web  and do it in Settings.`);
  process.exit(0);
} else if (cmd === "web") {
  const { startWeb } = await import("./web.ts");
  await startWeb({ port: Number(arg("port") || process.env.PORT || 5550), host: arg("host") || process.env.HOST || "127.0.0.1", version: VERSION });
} else {
  const text = (s: string) => ({ content: [{ type: "text" as const, text: s }] });
  const server = new McpServer({ name: "nyro", version: VERSION });

  server.registerTool(
    "scan_earnings",
    { title: "Scan mining earnings", description: "Read every configured payout wallet (EVM chains, Solana, Kaspa, Bitcoin) and list balances in USD, with what is new since the previous scan. Read-only.", inputSchema: {} },
    async () => {
      const s = await scanAll(loadConfig());
      return text([
        `Mined balance ${usd(s.totalUsd)}${s.demo ? " (DEMO)" : ""} · new since last scan ${usd(s.newUsd)}${s.previousAt ? ` (${new Date(s.previousAt).toISOString()})` : ""}`,
        "",
        "| Chain | Asset | Amount | New | Value |",
        "|---|---|---|---|---|",
        ...s.earnings.map((e) => `| ${e.chain} | ${e.symbol} | ${amt(e.amount)} | ${e.newAmount ? `+${amt(e.newAmount)}` : "–"} | ${usd(e.usd)} |`),
        ...s.warnings.map((w) => `⚠ ${w}`),
      ].join("\n"));
    },
  );

  server.registerTool(
    "get_settings",
    { title: "Nyro settings", description: "Show wallets, payout chain, Robinhood deposit addresses (set or not), harvest rules and allocation.", inputSchema: {} },
    async () => {
      const c = loadConfig();
      return text([
        `Mode: ${c.demo ? "DEMO" : "live"} · config ${fs.existsSync(configPath()) ? configPath() : "built-in demo defaults"}`,
        `Wallets: ${c.wallets.evm.length} EVM · ${c.wallets.solana.length} Solana · ${c.wallets.kaspa.length} Kaspa · ${c.wallets.bitcoin.length} Bitcoin`,
        `Payout: USDC on ${c.payout.chain} → ${c.payout.collectWallet || "first wallet of that family"}`,
        `Robinhood deposit: USDC ${c.payout.robinhood.USDC ? "set" : "not set"} · BTC ${c.payout.robinhood.BTC ? "set" : "not set"}`,
        `Rules: min ${usd(c.rules.minHarvestUsd)} · max route cost ${c.rules.maxCostPct}% · slippage ${c.rules.slippagePct}% · keep ${usd(c.rules.keepGasUsd)} gas`,
        `Allocation: ${c.allocation.map((a) => `${a.symbol} ${a.pct}%`).join(" · ") || "none"}`,
      ].join("\n"));
    },
  );

  server.registerTool(
    "set_rules",
    {
      title: "Set harvest rules",
      description: "Change when Nyro harvests: minimum value, maximum route cost (%), slippage, gas reserve, and the allocation split for Robinhood.",
      inputSchema: {
        minHarvestUsd: z.number().min(0).max(100000).optional(),
        maxCostPct: z.number().gt(0).max(50).optional(),
        slippagePct: z.number().min(0.05).max(5).optional(),
        keepGasUsd: z.number().min(0).max(1000).optional(),
        allocation: z.array(z.object({ symbol: z.string(), pct: z.number() })).optional(),
      },
    },
    async ({ allocation, ...rules }) => {
      const c = loadConfig();
      c.rules = { ...c.rules, ...Object.fromEntries(Object.entries(rules).filter(([, v]) => v !== undefined)) };
      const err = validateRules(c.rules) || (allocation ? validateAllocation(allocation.map((a) => ({ symbol: a.symbol.toUpperCase(), pct: a.pct }))) : null);
      if (err) return { ...text(err), isError: true };
      if (allocation) c.allocation = allocation.map((a) => ({ symbol: a.symbol.toUpperCase(), pct: a.pct }));
      saveConfig(c);
      return text("Saved.");
    },
  );

  server.registerTool(
    "plan_harvest",
    { title: "Plan a harvest", description: "For every mined token: harvest (live LI.FI route into USDC on the payout chain, with gas and fees) or hold (too small, too expensive, or no route). Then the Robinhood deposit and allocation steps. Nothing is sent.", inputSchema: {} },
    async () => {
      const cfg = loadConfig();
      const p = await buildPlan(await scanAll(cfg, { remember: false }), cfg);
      return text(renderPlan(p));
    },
  );

  server.registerTool(
    "get_transaction",
    { title: "Unsigned transaction for a leg", description: "Return the unsigned LI.FI transaction for one harvest leg, for the user to review and sign in their own wallet. Nyro never signs.", inputSchema: { plan_id: z.string(), leg: z.number().int().min(1) } },
    async ({ plan_id, leg }) => {
      const p = getPlan(plan_id);
      if (!p) return { ...text(`Unknown plan "${plan_id}". Run plan_harvest again.`), isError: true };
      if (Date.now() - p.createdAt > PLAN_TTL_MS) return { ...text("This plan expired (quotes move). Run plan_harvest again."), isError: true };
      const l = p.legs.find((x) => x.id === leg);
      if (!l?.tx) return { ...text(l ? "This leg has no transaction to sign (demo estimate, manual step, or a plain transfer)." : "No such leg."), isError: true };
      return text(`Leg ${leg}: ${l.detail}\nReview it in your wallet before signing:\n\n${JSON.stringify(l.tx, null, 2)}`);
    },
  );

  await server.connect(new StdioServerTransport());
}

