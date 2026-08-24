"""HTTP 어댑터는 stdio 어댑터와 같은 registry를 다른 전송 방식으로 노출할 뿐이다."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from adapters.http_server import build
from contracts.tool import ToolStatus
from router.registry import build_registry
from infra.settings import Settings
from tests.fakes import FakeDb, FakeLlm


@pytest.fixture
def client():
    cfg = Settings()
    llm = FakeLlm()
    registry = build_registry(FakeDb(), llm, cfg)
    return TestClient(build(registry=registry, llm=llm))


def test_health는_모듈별_상태를_돌려준다(client):
    body = client.get("/api/health").json()
    assert set(body["modules"]) == {"vector_search", "nl2sql", "knowledge_graph"}
    assert body["top_k"] and body["tau"]


def test_tools는_입력_스키마를_노출한다(client):
    tools = client.get("/api/tools").json()
    assert {t["name"] for t in tools} == {"vector_search", "nl2sql", "knowledge_graph"}
    assert all("properties" in t["input_schema"] for t in tools)


def test_ask는_답변과_라우팅_근거를_함께_돌려준다(client):
    body = client.post("/api/ask", json={"question": "Client-A가 사용 중인 제품은?"}).json()
    assert body["answer"]
    assert body["routing"]["tool"] in {"vector_search", "nl2sql", "knowledge_graph"}
    assert body["routing"]["stage"] in {"A", "C"}
    assert body["result"]["answer_basis"]["row_count"] == len(body["result"]["answer_basis"]["rows"])


def test_빈_질문은_422로_거절한다(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422


def test_미등록_모듈은_404다(client):
    assert client.post("/api/tools/없는도구", json={}).status_code == 404


def test_도구_호출_예외는_500이_아니라_계약_상태로_돌아온다(client):
    """stdio 경로와 같은 규칙 — 예외를 밖으로 던지지 않고 상태로 바꾼다."""
    body = client.post("/api/tools/knowledge_graph", json={"start_entity": None, "설명": 1}).json()
    assert body["status"] in {s.value for s in ToolStatus}
    assert body["answer_basis"]["unit"]
