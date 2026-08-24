"""웹 화면용 HTTP 어댑터. 전송 방식만 다를 뿐 stdio 어댑터와 같은 registry/router를 쓴다.

레이어 규칙상 전송은 adapter에 산다 — 이 파일은 service/domain을 건드리지 않고
Orchestrator.respond()와 Tool.run()을 JSON으로 옮기기만 한다.
"""
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from contracts.tool import ToolStatus, empty_result
from infra.db import PostgresDb
from infra.llm import OllamaClient
from infra.settings import Settings
from router.orchestrator import Orchestrator
from router.registry import build_registry, build_router

STATIC = Path(__file__).with_name("static")


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def build(registry=None, llm=None) -> FastAPI:
    cfg = Settings.from_env()
    if registry is None:
        llm = llm or OllamaClient(cfg.OLLAMA_URL, generate_model=cfg.GENERATE_MODEL, embed_model=cfg.EMBED_MODEL)
        registry = build_registry(PostgresDb(cfg.PG_DSN), llm, cfg)
    orchestrator = Orchestrator(build_router(registry, cfg), registry, llm)
    app = FastAPI(title="CompanyX MCP", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"modules": registry.health(), "generate_model": cfg.GENERATE_MODEL, "top_k": cfg.TOP_K, "tau": cfg.TAU}

    @app.get("/api/tools")
    def tools() -> list[dict[str, Any]]:
        return [{"name": name, "input_schema": spec.tool.input_schema(), "guideline": spec.guideline}
                for name, spec in registry.specs.items()]

    @app.post("/api/ask")
    def ask(body: Ask) -> dict[str, Any]:
        answered = orchestrator.respond(body.question.strip())
        decision = answered.decision
        return {
            "answer": answered.text,
            "considered": list(answered.considered),
            "routing": None if decision is None else {
                "tool": decision.tool, "confidence": round(decision.confidence, 4), "stage": decision.stage,
                "runner_up": None if decision.runner_up is None else
                             {"tool": decision.runner_up[0], "score": round(decision.runner_up[1], 4)},
                "entities": [getattr(e, "name", str(e)) for e in decision.entities],
            },
            "result": None if answered.result is None else asdict(answered.result),
        }

    @app.post("/api/tools/{name}")
    def call(name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = registry.tool(name)
        if tool is None: raise HTTPException(404, f"미등록 모듈: {name}")
        # 어댑터가 삼키지 못한 예외도 500이 아니라 계약상의 상태로 돌려준다 — stdio 경로와 같은 규칙이다.
        try: return asdict(tool.run(**params))
        except Exception as exc: return asdict(empty_result(name, ToolStatus.UPSTREAM_ERROR, unit="결과 없음", note=str(exc)))

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/")
        def index() -> FileResponse: return FileResponse(STATIC / "index.html")

    return app


app = None


def main() -> None:
    import uvicorn
    import os
    uvicorn.run(build(), host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8080")))


if __name__ == "__main__":
    main()
