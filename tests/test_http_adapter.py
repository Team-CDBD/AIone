"""HTTP 어댑터는 stdio 어댑터와 같은 registry를 다른 전송 방식으로 노출할 뿐이다."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from adapters.http_server import build
from contracts.tool import ToolStatus
from router.registry import build_registry
from infra.settings import Settings
from serverconf.service import ConnectionService
from tests.fakes import FakeDb, FakeLlm
from tests.test_server_connections import BASE, MemoryRepo, fake_probe


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


# --- 접속 프로필 전환 ---------------------------------------------------------
@pytest.fixture
def service(): return ConnectionService(MemoryRepo(), probe=fake_probe)


@pytest.fixture
def conn_client(service):
    llm = FakeLlm(generations=["답"] * 50)
    registry = build_registry(FakeDb(), llm, Settings())
    calls = []

    def factory(cfg):
        calls.append(cfg)
        if "boom" in cfg.PG_DSN: raise RuntimeError("조립 실패")
        return llm, registry

    made = TestClient(build(store=service, factory=factory))
    made.service, made.calls = service, calls
    return made


def test_프로필_목록과_현재_연결을_함께_돌려준다(conn_client):
    conn_client.service.create(BASE)
    body = conn_client.get("/api/connections").json()
    assert body["current"]["source"] == "환경변수" and body["current"]["profile_id"] is None
    assert [p["name"] for p in body["profiles"]] == ["운영"]


def test_생성_응답에_비밀번호가_없다(conn_client):
    body = conn_client.post("/api/connections", json=BASE).json()
    assert "s3cret" not in repr(body) and body["has_password"] is True


def test_잘못된_입력은_400과_한국어_사유다(conn_client):
    response = conn_client.post("/api/connections", json={**BASE, "tau": 9})
    assert response.status_code == 400 and "tau" in response.json()["detail"]


def test_없는_프로필_활성화는_404다(conn_client):
    assert conn_client.post("/api/connections/99/activate").status_code == 404


def test_활성화하면_그_프로필로_다시_붙는다(conn_client):
    created = conn_client.post("/api/connections", json=BASE).json()
    body = conn_client.post(f"/api/connections/{created['id']}/activate").json()
    assert body["activated"]["is_active"] is True
    assert conn_client.get("/api/health").json()["connection"] == {
        "source": "프로필 · 운영", "profile_id": created["id"], "store": True}
    assert conn_client.calls[-1].PG_DSN.endswith("db.local:5432/companyx")


def test_붙지_못하는_프로필은_활성이_되지_않는다(conn_client):
    """접속 확인에 실패하면 활성으로 기록하지도, 갈아끼우지도 않는다.

    커넥션 풀이 지연 접속이라 조립만으로는 판정할 수 없다 — 실제로 원격에서 없는 호스트의
    프로필이 '연결됨'으로 표시됐다. 그래서 activate는 rebind 전에 probe를 먼저 본다.
    """
    created = conn_client.post("/api/connections", json={**BASE, "pg_host": "unreachable"}).json()
    response = conn_client.post(f"/api/connections/{created['id']}/activate")
    assert response.status_code == 400 and "연결하지 못했습니다" in response.json()["detail"]
    assert conn_client.service.active() is None
    assert conn_client.get("/api/health").json()["connection"]["source"] == "환경변수"
    assert conn_client.post("/api/ask", json={"question": "Client-A가 사용 중인 제품은?"}).status_code == 200


def test_접속은_되는데_조립이_실패하면_기록도_되돌린다(conn_client):
    """probe는 통과했는데 rebind가 터지는 경우 — 화면과 DB가 어긋난 채 남으면 안 된다."""
    created = conn_client.post("/api/connections", json={**BASE, "pg_database": "boom"}).json()
    assert conn_client.post(f"/api/connections/{created['id']}/activate").status_code == 400
    assert conn_client.service.active() is None
    assert conn_client.get("/api/health").json()["connection"]["source"] == "환경변수"


def test_연결_중인_프로필은_삭제할_수_없다(conn_client):
    created = conn_client.post("/api/connections", json=BASE).json()
    conn_client.post(f"/api/connections/{created['id']}/activate")
    assert conn_client.delete(f"/api/connections/{created['id']}").status_code == 400
    assert conn_client.service.get(created["id"]) is not None


def test_환경변수로_되돌리면_활성이_해제된다(conn_client):
    created = conn_client.post("/api/connections", json=BASE).json()
    conn_client.post(f"/api/connections/{created['id']}/activate")
    assert conn_client.post("/api/connections/deactivate").json()["source"] == "환경변수"
    assert conn_client.service.active() is None


def test_저장소가_없으면_503이지_500이_아니다():
    llm = FakeLlm()
    registry = build_registry(FakeDb(), llm, Settings())
    made = TestClient(build(registry=registry, llm=llm))
    assert made.get("/api/connections").status_code == 503
    assert made.get("/api/health").json()["connection"]["store"] is False
