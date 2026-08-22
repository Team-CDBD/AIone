"""kg/wire.py, kg/client.py 계약 테스트. 실제 Java 프로세스는 없으므로 fake subprocess로 장애를 주입한다."""
import pytest
from kg.client import JenaGraphClient, JenaTimeout, ProcessError
from kg.wire import ALLOWED_RELATIONS, JenaRequest, JenaResponse, WireError


def _req(**over):
    base = dict(operation="traverse", start_entity="Client-A", relations=["USES"], target_types=["product"], max_hops=1, max_rows=100)
    base.update(over)
    return JenaRequest(**base)


def test_request_rejects_unknown_relation():
    with pytest.raises(WireError):
        _req(relations=["NOT_A_RELATION"])


def test_request_rejects_hop_out_of_range():
    with pytest.raises(WireError):
        _req(max_hops=3)


def test_response_rejects_row_width_mismatch():
    with pytest.raises(WireError):
        JenaResponse.from_json({"requestId": "r1", "status": "ok", "columns": ["id"], "rows": [["a", "b"]], "unit": "그래프 경로"})


def test_response_rejects_empty_unit():
    with pytest.raises(WireError):
        JenaResponse.from_json({"requestId": "r1", "status": "ok", "columns": [], "rows": [], "unit": ""})


def test_response_rejects_request_id_mismatch():
    with pytest.raises(WireError):
        JenaResponse.from_json({"requestId": "other", "status": "ok", "columns": [], "rows": [], "unit": "그래프 경로"}, expected_request_id="r1")


def test_response_ok_roundtrip():
    resp = JenaResponse.from_json({
        "requestId": "r1", "status": "ok", "columns": ["id", "name"], "rows": [["product_3", "Product-C3"]],
        "unit": "그래프 경로", "executedQuery": "template:uses-1hop", "sources": ["graph/nodes.json#id=product_3"],
    }, expected_request_id="r1")
    assert resp.rows == [["product_3", "Product-C3"]]
    assert resp.executed_query == "template:uses-1hop"


class _FakeStdin:
    def __init__(self, on_write=None): self.lines, self._on_write = [], on_write
    def write(self, s):
        if self._on_write: self._on_write()
        self.lines.append(s)
    def flush(self): pass
    def close(self): pass


class _FakeStdout:
    def __init__(self, responses): self._responses = list(responses)
    def readline(self): return self._responses.pop(0) if self._responses else ""


class _FakeProc:
    def __init__(self, responses, alive=True, on_write=None):
        self.stdin, self.stdout, self._alive = _FakeStdin(on_write), _FakeStdout(responses), alive
    def poll(self): return None if self._alive else 1
    def kill(self): self._alive = False
    def wait(self, timeout=None): return 0


def test_client_happy_path_uses_persistent_process():
    spawned = []
    def spawn(cmd):
        spawned.append(cmd)
        return _FakeProc([_ok_line("r-fixed"), _ok_line("r-fixed")])
    client = JenaGraphClient(["java", "-jar", "runner.jar"], spawn=spawn)
    req = _req(); object.__setattr__(req, "request_id", "r-fixed")
    resp = client.call(req)
    assert resp.status == "ok"
    assert len(spawned) == 1
    client.call(req)  # 두 번째 호출도 같은 프로세스 재사용
    assert len(spawned) == 1


def test_client_converts_malformed_json_to_wire_error():
    client = JenaGraphClient(["java"], spawn=lambda cmd: _FakeProc(["not-json\n"]))
    with pytest.raises(WireError):
        client.call(_req())


def test_client_restarts_once_then_gives_up():
    calls = {"n": 0}
    def spawn(cmd):
        calls["n"] += 1
        return _FakeProc([""])  # 항상 빈 응답 -> ProcessError
    client = JenaGraphClient(["java"], timeout_s=0.0, spawn=spawn)
    with pytest.raises(ProcessError):
        client.call(_req())
    assert calls["n"] == 1  # 최초 호출은 재기동을 쓰지 않음(쓰기 자체는 성공)


def test_client_health_false_when_spawn_fails():
    def spawn(cmd): raise OSError("no such file")
    client = JenaGraphClient(["java"], spawn=spawn)
    assert client.health() is False


def _ok_line(request_id: str) -> str:
    import json
    return json.dumps({"requestId": request_id, "status": "ok", "columns": ["id"], "rows": [["product_3"]], "unit": "그래프 경로"}) + "\n"
