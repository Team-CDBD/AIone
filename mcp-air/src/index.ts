// AirMCP main scaffold (§12.3). NOT the production entrypoint in this round —
// python -m adapters.mcp_sdk_server remains main until PR-7/PR-8 gates (A1~A7) pass.
// TypeScript owns schema/middleware/transport only; SQL Guard / KG planner / TACC composition
// stay in Python behind PythonWorker.call().
//
// NOTE: @airmcp-dev/core API surface (defineServer/defineTool exact shapes) is taken from the
// plan document's citation of the official Getting Started page, not independently re-verified
// against a live npm install in this environment (no network). Treat this file as a skeleton to
// be corrected against the real package API before P5 wiring.
import { defineServer, defineTool } from "@airmcp-dev/core";
import { z } from "zod";
import { PythonWorker } from "./python-worker.js";

const worker = new PythonWorker("python3", ["-m", "adapters.air_worker"], 30000);

async function airHandler(tool: string, params: Record<string, unknown>) {
  const envelope = await worker.call(tool, params);
  return envelope.result;
}

const server = defineServer({
  name: "companyx-mcp",
  version: "0.1.0-scaffold",
  transport: { type: "stdio" },
  use: [], // timeout/logging/meter 검증 후 추가 (§12.4 A5 게이트 통과 전에는 비움)
  tools: [
    defineTool("vector_search", {
      description: "Search CompanyX documents with pgvector and trigram RRF",
      params: {
        query: "string",
        doc_type: "string?",
        top_k: "number?",
      },
      handler: (params: Record<string, unknown>) => airHandler("vector_search", params),
    }),
    defineTool("nl2sql", {
      description: "Answer a structured CompanyX question using guarded read-only SQL",
      params: {
        question: "string",
        hint_tables: z.array(z.string()).optional(),
        max_rows: "number?",
      },
      handler: (params: Record<string, unknown>) => airHandler("nl2sql", params),
    }),
    defineTool("knowledge_graph", {
      description: "Traverse the CompanyX ontology graph",
      params: {
        start_entity: "string",
        relations: z.array(z.string()),
        target_types: z.array(z.string()),
        max_hops: "number?",
        aggregate: "string?",
      },
      handler: (params: Record<string, unknown>) => airHandler("knowledge_graph", params),
    }),
  ],
});

if (import.meta.url === `file://${process.argv[1]}`) {
  for (const signal of ["SIGTERM", "SIGINT"] as const) {
    process.once(signal, () => { worker.close(); process.exit(0); });
  }
  server.start().catch((err: unknown) => {
    process.stderr.write(`companyx-mcp: fatal ${String(err)}\n`);
    process.exit(1);
  });
}

export { server };
