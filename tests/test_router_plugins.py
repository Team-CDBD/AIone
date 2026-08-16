"""라우터가 특정 모듈을 몰라도 동작하는지 — 모듈 추가/교체/장애를 계약 수준에서 검증."""
from contracts.module import ModuleSpec, SignalSpec
from contracts.resolver import Resolution
from contracts.tool import AnswerBasis, Provenance, ToolName, ToolResult, ToolStatus, empty_result
from infra.settings import Settings
from router.registry import Registry, build_registry, build_router
from router.orchestrator import NO_ROUTE, Orchestrator
from router.resolvers import CompositeResolver
from router.stages import RuleRouter
from .fakes import FakeDb, FakeLlm

CFG = Settings()


class FakeTool:
    """어떤 언어로 구현되든 라우터가 보는 것은 이 표면뿐이다."""
    def __init__(self, name, rows=(("a",),), status=ToolStatus.OK):
        self.name, self.rows, self.status = name, [list(r) for r in rows], status
    def input_schema(self): return {"type": "object", "properties": {}, "additionalProperties": True}
    def health(self): return True
    def run(self, **params):
        return ToolResult(self.name, self.status, AnswerBasis(["c"], self.rows, len(self.rows), "건"),
                          Provenance(str(params)))


def spec_for(name, keywords, rows=(("a",),), status=ToolStatus.OK, resolver=None, weight=3.0):
    return ModuleSpec(
        tool=FakeTool(name, rows, status),
        signal=SignalSpec(tool=name, weight=weight, keywords=tuple(keywords)),
        build_params=lambda question, entities: {"q": question},
        tacc_profile="structured_aggregate", guideline="지침", resolver=resolver,
    )


def orchestrate(specs, question, llm=None):
    registry = Registry(specs)
    router = RuleRouter(registry.specs, tau=CFG.TAU)
    return Orchestrator(router, registry, llm).answer(question)


def test_unknown_module_routes_without_router_changes():
    """라우터 코드를 건드리지 않고 처음 보는 이름의 모듈로 라우팅된다."""
    answer = orchestrate([spec_for("weather_api", ["날씨"], rows=(("맑음",),))], "오늘 날씨 알려줘")
    assert "맑음" in answer


def test_registry_rejects_duplicate_module_names():
    try: Registry([spec_for("dup", ["가"]), spec_for("dup", ["나"])])
    except ValueError: return
    assert False, "duplicate module name must fail fast"


def test_spec_name_must_match_signal():
    try: ModuleSpec(tool=FakeTool("a"), signal=SignalSpec(tool="b"), build_params=lambda q, e: {})
    except ValueError: return
    assert False, "signal/tool name mismatch must fail fast"


def test_empty_registry_does_not_crash():
    assert orchestrate([], "아무 질문") == NO_ROUTE


def test_failing_module_is_ranked_last_not_fatal():
    """한 모듈이 죽어도 다른 모듈의 답이 나온다(Stage C)."""
    class Exploding(FakeTool):
        def run(self, **params): raise RuntimeError("java service down")
    broken = spec_for("remote_kg", ["담당"], status=ToolStatus.UPSTREAM_ERROR)
    broken = ModuleSpec(tool=Exploding("remote_kg"), signal=broken.signal,
                        build_params=broken.build_params, tacc_profile="relation_traversal")
    healthy = spec_for("docs", ["담당"], rows=(("문서",),))
    assert "문서" in orchestrate([broken, healthy], "담당 관련 담당 담당")


def test_resolver_failure_does_not_block_routing():
    """원격 모듈의 해소기가 죽어도 라우팅은 계속된다 — 라우터 전체 장애 방지."""
    class DeadResolver:
        def resolve(self, text): raise ConnectionError("down")
        def find_all(self, question): raise ConnectionError("down")
    composite = CompositeResolver([DeadResolver()])
    assert composite.find_all("Client-A") == []
    assert composite.resolve("Client-A").node_id is None
    assert "맑음" in orchestrate([spec_for("weather_api", ["날씨"], rows=(("맑음",),), resolver=DeadResolver())], "날씨")


def test_composite_resolver_prefers_higher_confidence():
    class Fixed:
        def __init__(self, resolution): self.resolution = resolution
        def resolve(self, text): return self.resolution
        def find_all(self, question): return [self.resolution]
    weak = Resolution("n1", "A", "client", 0.5, "fuzzy")
    strong = Resolution("n1", "A", "client", 1.0, "exact")
    assert CompositeResolver([Fixed(weak), Fixed(strong)]).resolve("A").confidence == 1.0


def test_default_registry_is_replaceable_by_providers():
    """DEFAULT_PROVIDERS를 갈아끼우면 kg 없이도 레지스트리가 구성된다."""
    def provide(db, llm, cfg): return spec_for("only_one", ["질문"])
    registry = build_registry(FakeDb([]), FakeLlm(), CFG, providers=[provide])
    assert list(registry) == ["only_one"]
    assert registry.health() == {"only_one": True}
    assert registry.tool("nope") is None


def test_yaml_weight_override_applies():
    def provide(db, llm, cfg): return spec_for("nl2sql", ["총"], weight=3.0)
    registry = build_registry(FakeDb([]), FakeLlm(), CFG, providers=[provide], rules={"weights": {"nl2sql": 9.0}})
    assert registry.spec("nl2sql").signal.weight == 9.0


def test_builtin_registry_still_exposes_three_tools():
    registry = build_registry(FakeDb([]), FakeLlm(), CFG)
    assert sorted(registry) == sorted(str(name) for name in ToolName)
    router = build_router(registry, CFG)
    decisions = router.route("2024년 총 매출은?")
    assert decisions and decisions[0].tool == ToolName.NL2SQL
    assert decisions[0].guideline
