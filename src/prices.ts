import { getJson } from "./http.ts";

/**
 * USD prices from DefiLlama's free coins API. Ids look like
 * "coingecko:solana", "solana:<mint>", "base:<erc20 address>".
 */
export async function getPrices(ids: string[]): Promise<Record<string, { price: number; symbol?: string }>> {
  const unique = [...new Set(ids)];
  const out: Record<string, { price: number; symbol?: string }> = {};
  for (let i = 0; i < unique.length; i += 80) {
    const chunk = unique.slice(i, i + 80);
    const r = await getJson<{ coins: Record<string, { price: number; symbol?: string }> }>(
      `https://coins.llama.fi/prices/current/${chunk.map(encodeURIComponent).join(",")}`,
    );
    Object.assign(out, r.coins);
  }
  return out;
}
