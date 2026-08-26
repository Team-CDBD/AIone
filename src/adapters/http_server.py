"""웹 화면용 HTTP 어댑터. 전송 방식만 다를 뿐 stdio 어댑터와 같은 registry/router를 쓴다.

레이어 규칙상 전송은 adapter에 산다 — 이 파일은 service/domain을 건드리지 않고
Orchestrator.respond()와 Tool.run()을 JSON으로 옮기기만 한다.

접속 대상은 더 이상 프로세스 수명 내내 고정이 아니다. Runtime이 registry/orchestrator를
들고 있고, 화면에서 프로필을 활성화하면 그 자리에서 다시 조립한다.
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
from serverconf.domain import ProfileInvalid
from serverconf.repository import ConnectionRepository
from serverconf.service import ConnectionService, ProfileNotFound
from serverconf.secrets import PasswordCipher

STATIC = Path(__file__).with_name("static")


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Runtime:
    """지금 어느 서버에 붙어 있는지를 들고 있는 유일한 곳.

    rebind()가 실패해도 이전 연결은 그대로 살아 있다 — 잘못된 프로필 하나로 화면 전체가
    죽으면 안 되기 때문이다. 실패는 예외로 올라가고 호출자가 상태로 바꾼다.
    """

    def __init__(self, cfg: Settings, factory=None, source: str = "환경변수"):
        self.factory = factory or connect
        self.rebind(cfg, source, None)

    def rebind(self, cfg: Settings, source: str, profile_id: int | None) -> None:
        llm, registry = self.factory(cfg)
        orchestrator = Orchestrator(build_router(registry, cfg), registry, llm)
        # 전부 만들어진 뒤에 한꺼번에 갈아끼운다 — 중간에 실패하면 이전 연결이 그대로 남는다.
        self.cfg, self.llm, self.registry, self.orchestrator = cfg, llm, registry, orchestrator
        self.source, self.profile_id = source, profile_id


def connect(cfg: Settings):
    """Settings → (llm, registry). 실제 접속이 일어나는 유일한 지점이라 테스트가 여기만 갈아끼운다."""
    llm = OllamaClient(cfg.OLLAMA_URL, generate_model=cfg.GENERATE_MODEL, embed_model=cfg.EMBED_MODEL)
    return llm, build_registry(PostgresDb(cfg.PG_DSN), llm, cfg)


def build(registry=None, llm=None, store: ConnectionService | None = None, factory=None) -> FastAPI:
    cfg = Settings.from_env()
    if store is None and cfg.CONFIG_PG_DSN:
        try:
            repo = ConnectionRepository(PostgresDb(cfg.CONFIG_PG_DSN), PasswordCipher(cfg.PROFILE_ENCRYPTION_KEY))
            repo.migrate_plaintext_passwords()
            store = ConnectionService(repo)
        except Exception: store = None  # 프로필 저장소가 없어도 질의 화면은 떠야 한다.

    if factory is None and registry is not None:
        fixed_llm = llm or OllamaClient(cfg.OLLAMA_URL, generate_model=cfg.GENERATE_MODEL, embed_model=cfg.EMBED_MODEL)
        factory = lambda _cfg: (fixed_llm, registry)  # noqa: E731 — 주입된 registry는 갈아끼우지 않는다.
    runtime = Runtime(cfg, factory=factory)
    # 저장된 활성 프로필이 있으면 환경변수보다 우선한다 — 마지막으로 고른 서버가 재기동 후에도 유지된다.
    if store is not None:
        try:
            active = store.active()
            if active is not None:
                runtime.rebind(store.settings_for(active.id, cfg), f"프로필 · {active.name}", active.id)
        except Exception: pass

    app = FastAPI(title="AIone", version="0.2.0")

    def need_store() -> ConnectionService:
        if store is None: raise HTTPException(503, "접속 프로필 저장소가 설정되지 않았습니다 (CONFIG_PG_DSN)")
        return store

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"modules": runtime.registry.health(), "generate_model": runtime.cfg.GENERATE_MODEL,
                "top_k": runtime.cfg.TOP_K, "tau": runtime.cfg.TAU,
                "connection": {"source": runtime.source, "profile_id": runtime.profile_id,
                               "store": store is not None}}

    @app.get("/api/tools")
    def tools() -> list[dict[str, Any]]:
        return [{"name": name, "input_schema": spec.tool.input_schema(), "guideline": spec.guideline}
                for name, spec in runtime.registry.specs.items()]

    @app.post("/api/ask")
    def ask(body: Ask) -> dict[str, Any]:
        answered = runtime.orchestrator.respond(body.question.strip())
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
        tool = runtime.registry.tool(name)
        if tool is None: raise HTTPException(404, f"미등록 모듈: {name}")
        # 어댑터가 삼키지 못한 예외도 500이 아니라 계약상의 상태로 돌려준다 — stdio 경로와 같은 규칙이다.
        try: return asdict(tool.run(**params))
        except Exception as exc: return asdict(empty_result(name, ToolStatus.UPSTREAM_ERROR, unit="결과 없음", note=str(exc)))

    # --- 접속 프로필 -------------------------------------------------------
    @app.get("/api/connections")
    def connections() -> dict[str, Any]:
        return {"profiles": [p.masked() for p in need_store().list()],
                "current": {"source": runtime.source, "profile_id": runtime.profile_id}}

    @app.post("/api/connections", status_code=201)
    def create(payload: dict[str, Any]) -> dict[str, Any]:
        return _guard(lambda: need_store().create(payload).masked())

    @app.put("/api/connections/{profile_id}")
    def update(profile_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return _guard(lambda: need_store().update(profile_id, payload).masked())

    @app.delete("/api/connections/{profile_id}")
    def delete(profile_id: int) -> dict[str, Any]:
        def run():
            if profile_id == runtime.profile_id:
                raise ProfileInvalid("지금 연결 중인 프로필은 삭제할 수 없습니다. 다른 프로필로 옮긴 뒤 삭제하세요")
            need_store().delete(profile_id)
            return {"deleted": profile_id}
        return _guard(run)

    @app.post("/api/connections/test")
    def test_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return _guard(lambda: need_store().probe(payload=payload))

    @app.post("/api/connections/{profile_id}/test")
    def test_saved(profile_id: int) -> dict[str, Any]:
        return _guard(lambda: need_store().probe(profile_id=profile_id))

    @app.post("/api/connections/{profile_id}/activate")
    def activate(profile_id: int) -> dict[str, Any]:
        def run():
            current = need_store()
            profile = current.get(profile_id)
            # 먼저 실제로 접속해 본다. rebind()만으로는 판정할 수 없다 — 커넥션 풀이 지연 접속이라
            # 존재하지 않는 호스트로도 조립은 성공하고, 첫 질의에 가서야 실패한다.
            probe = current.probe(profile_id=profile_id)
            if not probe["ok"]:
                reason = "; ".join(f"{n}: {c['detail']}" for n, c in probe["checks"].items() if c["ok"] is False)
                raise ProfileInvalid(f"연결하지 못했습니다 — {reason}")
            previous = (runtime.cfg, runtime.source, runtime.profile_id)
            activated = current.activate(profile_id)
            try: runtime.rebind(current.settings_for(profile_id, cfg), f"프로필 · {profile.name}", profile_id)
            except Exception as exc:
                # 기록은 됐는데 붙지 못했다면 둘 다 되돌린다 — 화면과 DB가 어긋난 채 남지 않는다.
                current.deactivate(); runtime.rebind(*previous)
                raise ProfileInvalid(f"연결하지 못했습니다: {type(exc).__name__}: {exc}") from exc
            return {"activated": activated.masked(), "probe": probe}
        return _guard(run)

    @app.post("/api/connections/deactivate")
    def deactivate() -> dict[str, Any]:
        def run():
            current = need_store()
            runtime.rebind(cfg, "환경변수", None)
            current.deactivate()
            return {"source": runtime.source, "modules": runtime.registry.health()}
        return _guard(run)

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/")
        def index() -> FileResponse: return FileResponse(STATIC / "index.html")

    return app


def _guard(action):
    """프로필 계열 오류는 500이 아니라 화면이 그대로 보여줄 수 있는 4xx로 내려간다."""
    try: return action()
    except ProfileInvalid as exc: raise HTTPException(400, str(exc)) from exc
    except ProfileNotFound as exc: raise HTTPException(404, str(exc)) from exc


app = None


def main() -> None:
    import uvicorn
    import os
    uvicorn.run(build(), host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8080")))


if __name__ == "__main__":
    main()
