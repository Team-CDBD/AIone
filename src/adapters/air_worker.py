"""AirMCP(TypeScript) main이 자식 프로세스로 기동하는 내부 JSONL worker.
mcp-air/src/python-worker.ts 가 {requestId, tool, params} 한 줄을 stdin에 쓰고 이 프로세스가
ToolResult JSON 한 줄을 stdout에 돌려준다. stdout은 JSONL 응답 전용, 진단 로그는 반드시 stderr로
분리한다(§12.3). Registry/Orchestrator는 시작 시 한 번만 만들고 반복 요청을 처리한다.
기존 src/adapters/mcp_sdk_server.py는 그대로 두고 이 worker는 별도 진입점으로만 추가한다."""
from __future__ import annotations
import json
import sys
from dataclasses import asdict
from typing import Any, TextIO

from contracts.tool import ToolStatus, empty_result
from infra.db import PostgresDb
from infra.llm import OllamaClient
from infra.settings import Settings
from router.registry import Registry, build_registry


def _log(message: str, *, stream: TextIO = sys.stderr) -> None:
    print(message, file=stream, flush=True)


def dispatch(registry: Registry, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("requestId")
    tool_name = request.get("tool")
    params = request.get("params") or {}
    tool = registry.tool(tool_name) if isinstance(tool_name, str) else None
    if tool is None:
        result = empty_result(tool_name or "unknown", ToolStatus.UPSTREAM_ERROR, unit="결과 없음",
                              note=f"미등록 모듈: {tool_name}")
    else:
        try:
            result = tool.run(**params)
        except Exception as exc:  # 어댑터가 놓친 예외도 프로세스를 죽이지 않는다
            result = empty_result(tool_name, ToolStatus.UPSTREAM_ERROR, unit="결과 없음", note=str(exc))
    return {"requestId": request_id, "result": asdict(result)}


def serve(registry: Registry, *, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    _log("air_worker: ready")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"air_worker: malformed request 무시 - {exc}")
            continue
        try:
            response = dispatch(registry, request)
        except Exception as exc:  # dispatch 자체가 실패해도 worker는 살아 있어야 한다
            response = {"requestId": request.get("requestId"), "result": asdict(
                empty_result(request.get("tool") or "unknown", ToolStatus.UPSTREAM_ERROR, unit="결과 없음", note=str(exc))
            )}
        print(json.dumps(response, ensure_ascii=False), file=stdout, flush=True)


def main() -> None:
    cfg = Settings.from_env()
    llm = OllamaClient(cfg.OLLAMA_URL, generate_model=cfg.GENERATE_MODEL, embed_model=cfg.EMBED_MODEL)
    registry = build_registry(PostgresDb(cfg.PG_DSN), llm, cfg)
    serve(registry)


if __name__ == "__main__":
    main()
