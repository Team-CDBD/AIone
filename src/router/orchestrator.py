from __future__ import annotations
from typing import Mapping

from contracts.infra import Llm, LlmError
from contracts.tool import Tool, ToolResult, ToolStatus, empty_result
from .domain.composer import fallback_table
from .domain.tacc import compose_context
from .stages import RouteDecision, RuleRouter

NO_ROUTE = "질문을 처리할 수 있는 모듈이 없습니다."


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

    def answer(self, question: str) -> str:
        decisions = self.router.route(question)
        if not decisions: return NO_ROUTE
        results = [self.call_tool(decision) for decision in decisions]
        ranked = sorted(zip(decisions, results),
                        key=lambda pair: (pair[1].status not in (ToolStatus.OK, ToolStatus.EMPTY),
                                          -pair[1].answer_basis.row_count))
        decision, result = ranked[0]
        if self.llm:
            context = compose_context(result, decision.tacc_profile, decision.guideline)
            try: return self.llm.generate(f"질문: {question}\n{context}\n근거만 사용해 한국어로 답하세요.")
            except LlmError: pass
        return fallback_table(result)
