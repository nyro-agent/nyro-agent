/**
 * Nyro web app: a JSON API over the same functions the MCP tools use, plus the static app in web/.
 *
 * Safety: binds to 127.0.0.1 by default (any other host needs NYRO_WEB_TOKEN as a Bearer token); API calls must come
 * from the app's own origin with the X-Nyro header (no CORS is ever sent); on loopback the Host header must be
 * localhost / 127.0.0.1 (DNS rebinding). Settings take public addresses only and refuse anything shaped like a key.
 */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import crypto from "node:crypto";
import {
  checkAddress, configPath, familyOf, loadConfig, PAYOUT_CHAINS, PKG_ROOT, saveConfig, validateAllocation, validateRules,
  type Config, type PayoutChain, type WalletFamily,
} from "./config.ts";
import { scanAll } from "./scan.ts";
import { buildPlan, getPlan, PLAN_TTL_MS } from "./plan.ts";

const WEB_DIR = path.join(PKG_ROOT, "web");
const TYPES: Record<string, string> = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp" };
const LOOPBACK = new Set(["127.0.0.1", "localhost", "::1"]);

class HttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
function send(res: http.ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" });
  res.end(JSON.stringify(body));
}
async function readJson(req: http.IncomingMessage): Promise<Record<string, unknown>> {
  if (!String(req.headers["content-type"] || "").startsWith("application/json")) throw new HttpError(415, "Send JSON.");
  let raw = "";
  for await (const chunk of req) { raw += chunk; if (raw.length > 32_768) throw new HttpError(413, "Request too large."); }
  try { return raw ? JSON.parse(raw) : {}; } catch { throw new HttpError(400, "Invalid JSON."); }
}

function list(value: unknown, family: WalletFamily): string[] {
  if (!Array.isArray(value)) throw new HttpError(400, `${family} wallets must be a list.`);
  const out: string[] = [];
  for (const raw of value) {
    const a = String(raw).trim();
    if (!a) continue;
    const err = checkAddress(family, a);
    if (err) throw new HttpError(400, err);
    if (!out.includes(a)) out.push(a);
  }
  if (out.length > 25) throw new HttpError(400, "Up to 25 wallets per family.");
  return out;
}
function optionalAddress(value: unknown, family: WalletFamily, label: string): string {
  const a = String(value ?? "").trim();
  if (!a) return "";
  const err = checkAddress(family, a);
  if (err) throw new HttpError(400, `${label}: ${err}`);
  return a;
}

function settings(c: Config, version: string) {
  return {
    version, demo: c.demo, forcedDemo: process.env.NYRO_DEMO === "1",
    wallets: c.wallets, payout: c.payout, rules: c.rules, allocation: c.allocation,
    payoutChains: PAYOUT_CHAINS, configPath: configPath(), configExists: fs.existsSync(configPath()), planTtlMs: PLAN_TTL_MS,
  };
}

async function api(method: string, route: string, req: http.IncomingMessage, version: string) {
  if (method === "GET" && route === "/api/settings") return settings(loadConfig(), version);

  if (method === "GET" && route === "/api/scan") return scanAll(loadConfig());

  if (method === "POST" && route === "/api/plan") {
    await readJson(req);
    const cfg = loadConfig();
    const plan = await buildPlan(await scanAll(cfg, { remember: false }), cfg);
    return { plan, expiresAt: plan.createdAt + PLAN_TTL_MS };
  }

  if (method === "GET" && route.startsWith("/api/tx/")) {
    const [, , , id, legStr] = route.split("/");
    const p = getPlan(id || "");
    if (!p) throw new HttpError(404, "Unknown plan. Build a new one.");
    if (Date.now() - p.createdAt > PLAN_TTL_MS) throw new HttpError(410, "This plan expired (quotes move). Build a new one.");
    const leg = p.legs.find((l) => l.id === Number(legStr));
    if (!leg?.tx) throw new HttpError(404, "This step has no transaction to sign.");
    return { leg: leg.id, detail: leg.detail, tx: leg.tx };
  }

  if (method === "POST" && route === "/api/settings") {
    const b = await readJson(req);
    const c = loadConfig();
    if (b.wallets !== undefined) {
      const w = b.wallets as Record<string, unknown>;
      c.wallets = { evm: list(w.evm ?? [], "evm"), solana: list(w.solana ?? [], "solana"), kaspa: list(w.kaspa ?? [], "kaspa"), bitcoin: list(w.bitcoin ?? [], "bitcoin") };
    }
    if (b.payout !== undefined) {
      const p = b.payout as Record<string, unknown>;
      const chain = String(p.chain) as PayoutChain;
      if (!PAYOUT_CHAINS.includes(chain)) throw new HttpError(400, "Unknown payout chain.");
      const fam = familyOf(chain);
      const rh = (p.robinhood || {}) as Record<string, unknown>;
      c.payout = {
        chain,
        collectWallet: optionalAddress(p.collectWallet, fam, "Collect wallet"),
        robinhood: { USDC: optionalAddress(rh.USDC, fam, `Robinhood USDC address (${chain})`), BTC: optionalAddress(rh.BTC, "bitcoin", "Robinhood BTC address") },
      };
    }
    if (b.rules !== undefined) {
      const r = b.rules as Record<string, unknown>;
      const rules = { minHarvestUsd: Number(r.minHarvestUsd), maxCostPct: Number(r.maxCostPct), slippagePct: Number(r.slippagePct), keepGasUsd: Number(r.keepGasUsd) };
      const err = validateRules(rules);
      if (err) throw new HttpError(400, err);
      c.rules = rules;
    }
    if (b.allocation !== undefined) {
      if (!Array.isArray(b.allocation)) throw new HttpError(400, "Allocation must be a list.");
      const a = (b.allocation as Record<string, unknown>[]).map((x) => ({ symbol: String(x.symbol || "").trim().toUpperCase(), pct: Number(x.pct) })).filter((x) => x.symbol);
      const err = validateAllocation(a);
      if (err) throw new HttpError(400, err);
      c.allocation = a;
    }
    if (b.demo !== undefined) {
      if (typeof b.demo !== "boolean") throw new HttpError(400, "demo must be true or false.");
      const n = c.wallets.evm.length + c.wallets.solana.length + c.wallets.kaspa.length + c.wallets.bitcoin.length;
      if (!b.demo && !n) throw new HttpError(400, "Add at least one mining payout wallet before going live.");
      c.demo = b.demo;
    }
    saveConfig(c);
    return settings(c, version);
  }

  throw new HttpError(404, "Unknown endpoint.");
}

function serveStatic(route: string, res: http.ServerResponse) {
  const rel = route === "/" ? "app.html" : decodeURIComponent(route).replace(/^\/+/, "");
  const file = path.resolve(WEB_DIR, rel);
  if (!file.startsWith(WEB_DIR + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    return res.end("Not found");
  }
  res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream", "cache-control": "no-cache", "x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer" });
  fs.createReadStream(file).pipe(res);
}

export async function startWeb({ port, host, version }: { port: number; host: string; version: string }) {
  const token = process.env.NYRO_WEB_TOKEN || "";
  const loopback = LOOPBACK.has(host);
  if (!loopback && token.length < 16) {
    console.error(`Refusing to listen on ${host} without NYRO_WEB_TOKEN (16+ characters). Anyone on the network could reach the API.`);
    process.exit(1);
  }
  const safeEq = (a: string, b: string) => a.length === b.length && crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));

  const server = http.createServer(async (req, res) => {
    const route = new URL(req.url || "/", "http://x").pathname;
    try {
      if (loopback) {
        const h = String(req.headers.host || "").replace(/:\d+$/, "").replace(/^\[|\]$/g, "");
        if (!LOOPBACK.has(h)) throw new HttpError(421, "Use http://127.0.0.1 or http://localhost.");
      }
      if (!route.startsWith("/api/")) {
        if (req.method !== "GET" && req.method !== "HEAD") throw new HttpError(405, "Method not allowed.");
        return serveStatic(route, res);
      }
      if (req.headers["x-nyro"] !== "1") throw new HttpError(403, "Missing X-Nyro header.");
      const origin = req.headers.origin;
      if (origin && origin !== `http://${req.headers.host}` && origin !== `https://${req.headers.host}`) throw new HttpError(403, "Cross-origin request blocked.");
      if (token && !safeEq(String(req.headers.authorization || ""), `Bearer ${token}`)) throw new HttpError(401, "Missing or wrong token.");
      send(res, 200, await api(req.method || "GET", route, req, version));
    } catch (e) {
      const err = e instanceof HttpError ? e : new HttpError(500, "Server error.");
      if (!(e instanceof HttpError)) console.error(e);
      send(res, err.status, { error: err.message });
    }
  });
  await new Promise<void>((resolve) => server.listen(port, host, resolve));
  const shown = host.includes(":") ? `[${host}]` : host;
  console.log(`nyro web ${version}

  App:       http://${shown}:${port}/
  Terminal:  http://${shown}:${port}/#terminal
  Mode:      ${loadConfig().demo ? "DEMO (sample mining wallets)" : "live wallets"}
${token ? "  Auth:      Bearer token required\n" : ""}
Ctrl+C to stop.`);
}
