// Runs every MCP tool once in demo mode, through a real MCP client over stdio.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({ command: "npx", args: ["tsx", "src/index.ts"], env: { ...process.env, NYRO_DEMO: "1" } as Record<string, string> });
const client = new Client({ name: "smoke", version: "0" });
await client.connect(transport);
const show = (name: string, res: unknown) => {
  const r = res as { content: { text: string }[]; isError?: boolean };
  console.log(`===== ${name}${r.isError ? " (error)" : ""}\n${r.content[0].text}\n`);
};

const tools = (await client.listTools()).tools.map((t) => t.name);
console.log("tools:", tools.join(", "), "\n");
for (const name of ["get_settings", "scan_earnings", "plan_harvest"]) show(name, await client.callTool({ name, arguments: {} }));
show("get_transaction (error)", await client.callTool({ name: "get_transaction", arguments: { plan_id: "nope", leg: 1 } }));
await client.close();
