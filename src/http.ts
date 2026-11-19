/** fetch with a timeout and a readable error. */
export async function getJson<T>(url: string, init: RequestInit = {}, timeoutMs = 15_000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    const text = await res.text();
    if (!res.ok) throw new Error(`${init.method || "GET"} ${new URL(url).host} -> HTTP ${res.status}: ${text.slice(0, 200)}`);
    return JSON.parse(text) as T;
  } finally {
    clearTimeout(t);
  }
}

export async function rpc<T>(url: string, method: string, params: unknown[]): Promise<T> {
  const r = await getJson<{ result?: T; error?: { message: string } }>(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (r.error) throw new Error(`${method}: ${r.error.message}`);
  return r.result as T;
}
