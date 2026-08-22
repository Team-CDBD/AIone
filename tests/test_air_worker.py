"""air_worker.py dispatch/serve 계약 테스트. 실 DB/LLM 없이 FakeDb/FakeLlm 기반 registry로 검증한다."""
import io
import json

from adapters.air_worker import dispatch, serve
from infra.settings import Settings
from router.registry import build_registry
from .fakes import FakeDb, FakeLlm


def _registry():
    return build_registry(FakeDb([{"id": "c1", "name": "Client-A"}]), FakeLlm(), Settings())


def test_dispatch_ok_wraps_tool_result():
    registry = _registry()
    response = dispatch(registry, {
        "requestId": "r1", "tool": "knowledge_graph",
        "params": {"start_entity": "Client-A", "relations": [], "target_types": []},
    })
    assert response["requestId"] == "r1"
    assert response["result"]["tool"] == "knowledge_graph"
    assert response["result"]["status"] in ("ok", "empty", "entity_not_found", "upstream_error")


def test_dispatch_unknown_tool_is_upstream_error():
    registry = _registry()
    response = dispatch(registry, {"requestId": "r2", "tool": "no_such_tool", "params": {}})
    assert response["result"]["status"] == "upstream_error"


def test_serve_survives_malformed_line_and_keeps_processing():
    registry = _registry()
    stdin = io.StringIO("not-json\n" + json.dumps({"requestId": "r3", "tool": "no_such_tool", "params": {}}) + "\n")
    stdout = io.StringIO()
    serve(registry, stdin=stdin, stdout=stdout)
    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["requestId"] == "r3"
