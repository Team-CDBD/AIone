from dataclasses import dataclass
from .ontology import NodeType, ONTOLOGY, Relation

class PlanError(ValueError): pass
@dataclass(frozen=True)
class TraversalPlan:
    start_id: str; relations: tuple[Relation, ...]; target_types: tuple[NodeType, ...]; max_hops: int; aggregate: str | None = None

def plan(start_id: str, start_type: NodeType, relations: list[str], target_types: list[str], max_hops: int, aggregate: str | None = None) -> TraversalPlan:
    if not start_id: raise PlanError("start node is required")
    if not 1 <= max_hops <= 2: raise PlanError("max_hops must be between 1 and 2")
    try:
        rels = tuple(Relation(item) for item in relations)
        targets = tuple(NodeType(item) for item in target_types)
    except ValueError as exc: raise PlanError(str(exc)) from exc
    reachable = {start_type}
    for _ in range(max_hops):
        next_types = set(reachable)
        for rel in rels:
            spec = ONTOLOGY[rel]
            if spec.domain in reachable: next_types.add(spec.range_)
            if spec.range_ in reachable: next_types.add(spec.domain)
        reachable = next_types
    if targets and not set(targets) & reachable: raise PlanError("target type is unreachable with selected relations")
    return TraversalPlan(start_id, rels, targets, max_hops, aggregate)

@dataclass(frozen=True)
class GlobalPlan:
    """시작 개체 없이 관계 전체를 집계하는 계획. side는 그룹핑할 엣지 끝점이다."""
    relation: Relation; target_type: NodeType; side: str; aggregate: str | None; neighbor_filter: dict[str, str]; limit: int

def plan_global(relation: str, target_type: str, aggregate: str | None = None,
                neighbor_filter: dict[str, str] | None = None, limit: int = 10) -> GlobalPlan:
    try:
        rel = Relation(relation); target = NodeType(target_type)
    except ValueError as exc: raise PlanError(str(exc)) from exc
    spec = ONTOLOGY[rel]
    # 그룹핑 노드는 반드시 관계의 끝점이어야 한다 — 온톨로지가 방향을 결정하고 호출자는 못 고른다.
    if target is spec.domain: side = "source"
    elif target is spec.range_: side = "target"
    else: raise PlanError("target type is not an endpoint of the relation")
    if aggregate not in (None, "count"): raise PlanError("unsupported aggregate")
    if not 1 <= limit <= 100: raise PlanError("limit must be between 1 and 100")
    return GlobalPlan(rel, target, side, aggregate, dict(neighbor_filter or {}), limit)

_GLOBAL_UNITS = {
    (Relation.REPORTED_ISSUE, NodeType.PRODUCT): "제품별 이슈 제기 고객사 수",
    (Relation.MANAGES_ACCOUNT, NodeType.EMPLOYEE): "직원별 담당 고객사 수",
    (Relation.LEADS, NodeType.EMPLOYEE): "직원별 담당 프로젝트 수",
    (Relation.USES, NodeType.PRODUCT): "제품별 사용 고객사 수",
    (Relation.HAS_PROJECT, NodeType.CLIENT): "고객사별 프로젝트 수",
}

def global_unit(relation: Relation, target_type: NodeType) -> str:
    return _GLOBAL_UNITS.get((relation, target_type), f"{target_type.value}별 연결 개체 수")

def aggregate_unit(relation: Relation | None, mode: str | None) -> str:
    if relation is Relation.REPORTED_ISSUE: return "기술지원 이슈를 제기한 고유 고객사 수"
    if mode == "count": return "연결 개체 수"
    return "그래프 경로"
