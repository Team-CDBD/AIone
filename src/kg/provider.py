from __future__ import annotations
from typing import Any, Sequence

from contracts.module import ModuleSpec, SignalSpec
from contracts.resolver import Resolution
from contracts.tool import ToolName
from .adapter import KnowledgeGraphTool
from .domain.ontology import ONTOLOGY, Relation
from .repository import KgRepository
from .resolver import KgEntityResolver
from .service import GraphService

SIGNAL = SignalSpec(
    tool=ToolName.KNOWLEDGE_GRAPH,
    weight=3.5,
    keywords=("담당","소속","사용 중인","이끄는","팀장","누구야","관련된","기술 지원 이슈"),
    entity_when="present",
    entity_bonus=2.0,
)
GUIDELINE = "그래프 경로의 방향과 단위를 명시하세요."
# 질문 키워드 → 온톨로지 관계. 라우터가 아니라 kg 모듈이 소유한다.
RELATION_BY_KEYWORD = {"소속":"BELONGS_TO","팀장":"HEAD_IS","사용":"USES","담당":"MANAGES_ACCOUNT","프로젝트":"HAS_PROJECT","이끄":"LEADS","이슈":"REPORTED_ISSUE"}
DEFAULT_RELATIONS = ["USES", "HAS_PROJECT"]
MAX_HOPS = 2
# 시작 개체 없이 관계 전체를 훑어야 하는 질문의 표지.
AGGREGATE_TRIGGERS = ("가장 많", "가장 적", "최다", "제일 많")
# 이웃 노드 property 필터. 값은 데이터셋 enum 그대로다.
NEIGHBOR_FILTERS = {"진행 중": ("status", "in_progress"), "완료된": ("status", "completed"),
                    "보류": ("status", "on_hold"), "계획 중": ("status", "planning")}
TYPE_KEYWORDS = (("project", ("프로젝트",)), ("client", ("고객사", "고객")), ("product", ("제품",)),
                 ("employee", ("직원", "팀장", "엔지니어", "담당자")), ("department", ("부서",)))


def _last_mentioned_type(question: str) -> str | None:
    """전역 질문의 답 유형은 보통 문장 끝의 명사다 — '…고객을 담당하는 직원은?' → employee."""
    best, best_at = None, -1
    for node_type, words in TYPE_KEYWORDS:
        at = max((question.rfind(word) for word in words), default=-1)
        if at > best_at: best, best_at = node_type, at
    return best


def _global_params(question: str, relations: list[str]) -> dict[str, Any] | None:
    aggregated = any(trigger in question for trigger in AGGREGATE_TRIGGERS)
    neighbor_filter = {key: value for phrase, (key, value) in NEIGHBOR_FILTERS.items() if phrase in question}
    if not aggregated and not neighbor_filter: return None
    target = _last_mentioned_type(question)
    if target is None: return None
    # 답 유형이 끝점인 관계만 전역 집계가 가능하다. '진행 중인 프로젝트를 이끄는 직원'처럼
    # 키워드가 여러 관계를 집어내면 온톨로지가 유효한 쪽(LEADS)을 고른다.
    relation = next((rel for rel in relations
                     if target in (ONTOLOGY[Relation(rel)].domain, ONTOLOGY[Relation(rel)].range_)), None)
    if relation is None: return None
    return {"scope": "global", "relation": relation, "target_type": target,
            "aggregate": "count" if aggregated else None, "neighbor_filter": neighbor_filter,
            "limit": 5 if aggregated else 100}


def build_params(question: str, entities: Sequence[Resolution]) -> dict[str, Any]:
    named = next((e.name for e in entities if e.name), None)
    relations = [rel for keyword, rel in RELATION_BY_KEYWORD.items() if keyword in question] or list(DEFAULT_RELATIONS)
    if named is None:
        params = _global_params(question, relations)
        if params is not None: return params
    start = named or question
    if "Product-" in question and "프로젝트" in question: relations = ["USES", "HAS_PROJECT"]
    if "프로젝트" in question: targets = ["project"]
    elif "고객사" in question or "고객" in question: targets = ["client"]
    elif "제품" in question: targets = ["product"]
    elif "직원" in question or "팀장" in question or "엔지니어" in question: targets = ["employee"]
    else: targets = []
    hops = 2 if len(relations) > 1 else 1
    return {"start_entity": start, "relations": relations, "target_types": targets, "max_hops": hops}


def provide(db: Any, llm: Any, cfg: Any) -> ModuleSpec:
    repo = KgRepository(db)
    resolver = KgEntityResolver(repo)
    engine = getattr(cfg, "KG_ENGINE", "python")
    # engine=="jena"/"shadow"는 이번 라운드 스코프 밖(§P3 실연결 미구현) — client.py는 배선만 되어 있고
    # 항상 Python traversal로 조립한다. 실제 분기는 JenaGraphClient가 typed traversal을 반환하게 되는
    # 다음 라운드에서 GraphService에 연결한다.
    if engine in ("jena", "shadow"):
        pass
    return ModuleSpec(
        tool=KnowledgeGraphTool(GraphService(repo, resolver)),
        signal=SIGNAL, build_params=build_params,
        tacc_profile="relation_traversal", guideline=GUIDELINE,
        resolver=resolver,
    )
