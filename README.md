# NYRO · AI mining agent

Nyro watches your mining, staking, node and farm payout wallets on **Solana, Ethereum, Base, Arbitrum, Polygon,
Kaspa and Bitcoin**, shows what came in, prices what it would cost to move each reward (live **LI.FI** routes:
gas + bridge + swap fees), holds what is not worth it, and plans the rest into **USDC** on one chain and on to your
**Robinhood** deposit address, with a suggested split (for example 70% NVDA, 30% BTC).

It is an MCP server for AI agents plus a local web app (dashboard, harvest plan, terminal, settings).

## Safety model

- **Public addresses only.** Anything shaped like a private key or seed phrase is refused.
- **Nyro never signs or sends.** Every on-chain step is an unsigned LI.FI transaction you review and sign in your own wallet.
- **Fees before moves.** Rewards under `minHarvestUsd`, or routes costing more than `maxCostPct`, are held.
- **Gas reserve.** `keepGasUsd` of each native coin stays behind.
- **Fresh quotes.** Plans expire after 10 minutes.
- **No brokerage access.** Robinhood buys are instructions you place yourself. Check in the Robinhood app which
  networks it accepts for each coin before sending; the wrong network can lose funds.

## Quick start

```bash
npx -y nyro-agent web          # http://127.0.0.1:5550  (from source: npm install && npm run build && node dist/index.js web)
```

Starts in **demo mode** (sample GPU rig, DePIN node, staking and farm wallets, estimated costs).
In Settings: add payout addresses, pick the payout chain, paste your Robinhood deposit addresses, switch to Live.

MCP client:

```json
{ "mcpServers": { "nyro": { "command": "npx", "args": ["-y", "nyro-agent"] } } }
```

## MCP tools

| Tool | What it does | Moves money? |
|---|---|---|
| `scan_earnings` | Balances in every payout wallet, and what is new since the last scan | No |
| `plan_harvest` | Harvest or hold each token, with live LI.FI costs, then the Robinhood deposit and split | No |
| `get_transaction` | The unsigned transaction for one step, to sign in your wallet | No |
| `get_settings` | Wallets, payout chain, Robinhood addresses, rules and split | No |
| `set_rules` | Minimum value, max route cost, slippage, gas reserve, split | No |

Web terminal: `scan`, `plan`, `tx <plan_id> <step>`, `rules`, `set min <usd>`, `set maxcost <pct>`.

## How each chain is handled

| Chain | Read from | Route |
|---|---|---|
| Ethereum, Base, Arbitrum, Polygon | public RPCs (native coin + listed ERC-20s) | LI.FI into USDC on the payout chain |
| Solana | public RPC (SOL + every priced SPL / Token-2022 token) | LI.FI (same-chain swap or bridge) |
| Bitcoin | Blockstream Esplora, mempool.space fallback | sent straight to your Robinhood BTC address |
| Kaspa | api.kaspa.org | manual: sell on an exchange that lists KAS (no bridge route exists) |

Prices: DefiLlama. Settings live in `~/.nyro` (`NYRO_HOME`, `NYRO_CONFIG`, `NYRO_DEMO=1`, `NYRO_WEB_TOKEN`).

## Web app security

Listens on `127.0.0.1` only. `--host 0.0.0.0` refuses to start without `NYRO_WEB_TOKEN` (16+ characters).
API calls need the app's own origin and an `X-Nyro` header, so other websites in your browser cannot use it;
on loopback the Host header must be localhost (blocks DNS rebinding).

## Website (`site/`)

Static landing page for **nyro.run** (canonical, Open Graph, `robots.txt`, `sitemap.xml`, `404.html`).
Deploy the `site` folder to any static host (Vercel / Netlify / Cloudflare Pages: output directory `site`, no build).
"Open app" points to `http://127.0.0.1:5550`; set `window.NYRO_APP_URL` if you host the app elsewhere.

## Folders

| Folder | What is in it |
|---|---|
| `src/`, `web/`, `scripts/` | The agent: MCP server, web app, smoke test |
| `site/` | Landing page for nyro.run |
| `deploy/` | `deploy.sh` (upload `site/`), `setup-domain.sh` (one-time HTTPS), `nginx.conf.tpl` |
| `brand/NYRO-X/` | X profile: avatar, header 1500 + 3000, share image, white logo, `bio.txt` |
| `brand/logo/` | Mark (SVG, PNG), wordmarks, 3D coin, profile photos |
| `brand/source/` | Blender + Python sources for the coin, banner and logo renders |
| `konten-x/` | X posts: `pre/`, `post/`, `video/`, `captions.txt`, source in `_src/` (local only, git-ignored) |

## Develop

```bash
npm install
npm run smoke       # every MCP tool once, demo mode
npm run typecheck
npm run build       # dist/index.js
```

## Roadmap

1. Sign from the app with a connected browser wallet
2. Claim transactions for staking and DePIN programs
3. Scheduled scans with a notification when a harvest is worth signing

Not financial advice. MIT.
