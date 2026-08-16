from __future__ import annotations
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from contracts.module import ModuleProvider, ModuleSpec, SignalSpec
from contracts.tool import Tool
from infra.settings import Settings
from .resolvers import CompositeResolver
from .stages import RuleRouter

RULES_PATH = Path(__file__).with_name("rules") / "router_rules.yaml"

# 모듈을 붙이거나 떼는 유일한 지점. 언어·전송 방식이 달라도 provide()가 ModuleSpec만 돌려주면 된다.
DEFAULT_PROVIDERS: tuple[str, ...] = (
    "vector.provider:provide",
    "nl2sql.provider:provide",
    "kg.provider:provide",
)


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    """tau/delta/weights 튜닝값. 파일이 없거나 깨져도 기본값으로 동작한다."""
    try:
        import yaml
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _load(reference: str | ModuleProvider) -> ModuleProvider:
    if callable(reference): return reference
    from importlib import import_module
    module_name, _, attribute = str(reference).partition(":")
    return getattr(import_module(module_name), attribute or "provide")


class Registry(Mapping[str, Tool]):
    """이름 → Tool 매핑(기존 사용처 호환)이면서, 라우터에는 ModuleSpec을 노출한다."""

    def __init__(self, specs: Sequence[ModuleSpec]):
        self._specs: dict[str, ModuleSpec] = {}
        for spec in specs:
            if spec.name in self._specs: raise ValueError(f"duplicate module name: {spec.name}")
            self._specs[spec.name] = spec

    def __getitem__(self, key: str) -> Tool: return self._specs[str(key)].tool
    def __iter__(self) -> Iterator[str]: return iter(self._specs)
    def __len__(self) -> int: return len(self._specs)

    @property
    def specs(self) -> dict[str, ModuleSpec]: return dict(self._specs)
    def spec(self, name: str) -> ModuleSpec | None: return self._specs.get(str(name))
    def tool(self, name: str) -> Tool | None:
        spec = self.spec(name); return spec.tool if spec else None
    def resolvers(self) -> CompositeResolver:
        return CompositeResolver([s.resolver for s in self._specs.values() if s.resolver is not None])
    def health(self) -> dict[str, bool]:
        out = {}
        for name, spec in self._specs.items():
            try: out[name] = bool(spec.tool.health())
            except Exception: out[name] = False
        return out


def build_registry(db, llm, cfg: Settings, providers: Sequence[str | ModuleProvider] | None = None,
                   rules: dict[str, Any] | None = None) -> Registry:
    rules = load_rules() if rules is None else rules
    weights = rules.get("weights") or {}
    specs = []
    for reference in (providers if providers is not None else DEFAULT_PROVIDERS):
        spec = _load(reference)(db, llm, cfg)
        if not isinstance(spec, ModuleSpec): raise TypeError(f"{reference} must return ModuleSpec")
        if spec.name in weights: spec = _reweighted(spec, float(weights[spec.name]))
        specs.append(spec)
    return Registry(specs)


def _reweighted(spec: ModuleSpec, weight: float) -> ModuleSpec:
    from dataclasses import replace
    return replace(spec, signal=spec.signal.with_weight(weight))


def build_router(registry: Registry, cfg: Settings, rules: dict[str, Any] | None = None) -> RuleRouter:
    rules = load_rules() if rules is None else rules
    delta = rules.get("delta")
    return RuleRouter(registry.specs, registry.resolvers(), tau=cfg.TAU,
                      delta=float(delta) if delta is not None else None)


def default_signals() -> list[SignalSpec]:
    """DB/LLM 없이 신호 카탈로그만 필요할 때(테스트·라우팅 진단용)."""
    signals = []
    for reference in DEFAULT_PROVIDERS:
        from importlib import import_module
        signals.append(getattr(import_module(str(reference).partition(":")[0]), "SIGNAL"))
    return signals
