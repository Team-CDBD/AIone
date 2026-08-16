from dataclasses import asdict

from contracts.tool import ToolName, ToolStatus, empty_result
from infra.db import PostgresDb
from infra.llm import OllamaClient
from infra.settings import Settings
from router.registry import build_registry


def create_server(registry=None):
    from mcp.server.mcpserver import MCPServer

    cfg = Settings.from_env()
    if registry is None:
        llm = OllamaClient(cfg.OLLAMA_URL, generate_model=cfg.GENERATE_MODEL, embed_model=cfg.EMBED_MODEL)
        registry = build_registry(PostgresDb(cfg.PG_DSN), llm, cfg)
    server = MCPServer("companyx", version="0.1.0")

    def run(name: str, **params) -> dict:
        tool = registry.tool(name)
        if tool is None:
            return asdict(empty_result(name, ToolStatus.UPSTREAM_ERROR, unit="결과 없음", note=f"미등록 모듈: {name}"))
        return asdict(tool.run(**params))

    @server.tool(name="vector_search", description="Search CompanyX documents with pgvector and trigram RRF")
    def vector_search(query: str, doc_type: str | None = None, top_k: int | None = None) -> dict:
        return run(ToolName.VECTOR_SEARCH, query=query, doc_type=doc_type, top_k=top_k)

    @server.tool(name="nl2sql", description="Answer a structured CompanyX question using guarded read-only SQL")
    def nl2sql(question: str, hint_tables: list[str] | None = None, max_rows: int = 100) -> dict:
        return run(ToolName.NL2SQL, question=question, hint_tables=hint_tables or [], max_rows=max_rows)

    @server.tool(name="knowledge_graph", description="Traverse the CompanyX ontology graph")
    def knowledge_graph(
        start_entity: str,
        relations: list[str],
        target_types: list[str],
        max_hops: int = 2,
        aggregate: str | None = None,
    ) -> dict:
        return run(ToolName.KNOWLEDGE_GRAPH, start_entity=start_entity, relations=relations,
                   target_types=target_types, max_hops=max_hops, aggregate=aggregate)

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
