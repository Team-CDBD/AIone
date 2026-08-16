from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol, Sequence

from .resolver import EntityResolver, Resolution
from .tool import Tool


@dataclass(frozen=True)
class SignalSpec:
    """모듈이 스스로 신고하는 라우팅 신호. 라우터는 이 데이터만 보고 점수를 낸다."""
    tool: str
    weight: float = 3.0
    keywords: tuple[str, ...] = ()
    pattern: str | None = None
    pattern_bonus: float = 0.0
    pattern_label: str = "pattern"
    entity_when: Literal["present", "absent"] | None = None
    entity_bonus: float = 0.0

    def with_weight(self, weight: float) -> "SignalSpec":
        from dataclasses import replace
        return replace(self, weight=weight)


@dataclass(frozen=True)
class ModuleSpec:
    """라우터가 한 모듈에 대해 알아야 하는 전부. 언어·구현·전송 방식은 tool 뒤에 숨는다."""
    tool: Tool
    signal: SignalSpec
    build_params: Callable[[str, Sequence[Resolution]], dict[str, Any]]
    tacc_profile: str = "fallback_ambiguous"
    guideline: str = ""
    resolver: EntityResolver | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def name(self) -> str: return str(self.tool.name)

    def __post_init__(self) -> None:
        if self.signal.tool != self.name:
            raise ValueError(f"signal.tool({self.signal.tool}) != tool.name({self.name})")
        if not callable(self.build_params):
            raise ValueError("build_params must be callable")


class ModuleProvider(Protocol):
    """(db, llm, cfg) -> ModuleSpec. 모듈을 라우터에 꽂는 유일한 진입점."""
    def __call__(self, db: Any, llm: Any, cfg: Any) -> ModuleSpec: ...
