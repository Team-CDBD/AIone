from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Mapping

from contracts.infra import Llm, LlmError
from contracts.tool import Tool, ToolResult, ToolStatus, empty_result
from .domain.composer import fallback_table
from .domain.tacc import compose_context
from .stages import RouteDecision, RuleRouter

NO_ROUTE = "질문을 처리할 수 있는 모듈이 없습니다."


@dataclass(frozen=True)
class Answer:
    """answer()가 문자열만 돌려주면 어느 모듈이 왜 이겼는지가 사라진다. 화면·감사에는 그 근거가 필요하다."""
    text: str
    decision: RouteDecision | None = None
    result: ToolResult | None = None
    considered: tuple[str, ...] = ()


class Orchestrator:
    def __init__(self, router: RuleRouter, registry: Mapping[str, Tool], llm: Llm | None = None):
        self.router, self.registry, self.llm = router, registry, llm

    def call_tool(self, decision: RouteDecision) -> ToolResult:
        tool = self.registry.get(decision.tool) if hasattr(self.registry, "get") else self.registry[decision.tool]
        if tool is None:
            return empty_result(decision.tool, ToolStatus.UPSTREAM_ERROR, unit="결과 없음",
                                note=f"등록되지 않은 모듈: {decision.tool}")
        try: return tool.run(**decision.params)
        except Exception as exc:  # 어댑터가 삼키지 못한 예외도 라우팅을 중단시키지 않는다
            return empty_result(decision.tool, ToolStatus.UPSTREAM_ERROR, unit="결과 없음", note=str(exc))

    def call_tools(self, decisions):
        """Stage C는 전 모듈을 실행한다. 직렬로 돌면 가장 느린 모듈이 아니라 모든 모듈의 합이 지연이 된다.
        call_tool이 예외를 삼키므로 한 모듈이 죽어도 나머지 결과는 그대로 온다."""
        if len(decisions) == 1: return [self.call_tool(decisions[0])]
        with ThreadPoolExecutor(max_workers=len(decisions)) as pool:
            return list(pool.map(self.call_tool, decisions))

    def answer(self, question: str) -> str:
        return self.respond(question).text

    def respond(self, question: str) -> Answer:
        decisions = self.router.route(question)
        if not decisions: return Answer(NO_ROUTE)
        results = self.call_tools(decisions)
        ranked = sorted(zip(decisions, results),
                        key=lambda pair: (pair[1].status not in (ToolStatus.OK, ToolStatus.EMPTY),
                                          -pair[1].answer_basis.row_count))
        decision, result = ranked[0]
        considered = tuple(item.tool for item in decisions)
        if self.llm:
            context = compose_context(result, decision.tacc_profile, decision.guideline)
            try: return Answer(self.llm.generate(f"질문: {question}\n{context}\n근거만 사용해 한국어로 답하세요."),
                               decision, result, considered)
            except LlmError: pass
        return Answer(fallback_table(result), decision, result, considered)
