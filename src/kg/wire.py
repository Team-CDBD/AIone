"""Java runner(Jena) JSONL 프로토콜의 요청/응답 DTO. §5.1/§5.2 계약을 그대로 dataclass로 표현한다.
I/O는 하지 않는다 — 직렬화/검증 순수 함수만 둔다."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import uuid

ALLOWED_OPERATIONS = ("traverse", "aggregate")
ALLOWED_RELATIONS = ("BELONGS_TO", "HEAD_IS", "USES", "MANAGES_ACCOUNT", "HAS_PROJECT", "LEADS", "REPORTED_ISSUE")
ALLOWED_TARGET_TYPES = ("client", "product", "employee", "project", "department")
ALLOWED_STATUS = ("ok", "empty", "entity_not_found", "guard_rejected", "timeout", "upstream_error")
MAX_HOPS = 2
MAX_ROWS = 1000


class WireError(RuntimeError):
    """요청/응답이 wire 계약을 위반했을 때. client.py가 이를 삼켜 upstream_error/timeout으로 변환한다."""


@dataclass(frozen=True)
class JenaRequest:
    operation: str
    start_entity: str
    relations: list[str] = field(default_factory=list)
    target_types: list[str] = field(default_factory=list)
    max_hops: int = 1
    aggregate: str | None = None
    max_rows: int = 100
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.operation not in ALLOWED_OPERATIONS:
            raise WireError(f"알 수 없는 operation: {self.operation}")
        if not self.start_entity.strip():
            raise WireError("start_entity가 비어 있습니다")
        if any(r not in ALLOWED_RELATIONS for r in self.relations):
            raise WireError("허용되지 않은 relation이 포함되어 있습니다")
        if any(t not in ALLOWED_TARGET_TYPES for t in self.target_types):
            raise WireError("허용되지 않은 target_type이 포함되어 있습니다")
        if not (1 <= self.max_hops <= MAX_HOPS):
            raise WireError(f"max_hops는 1~{MAX_HOPS} 범위여야 합니다")
        if not (1 <= self.max_rows <= MAX_ROWS):
            raise WireError(f"max_rows는 1~{MAX_ROWS} 범위여야 합니다")

    def to_json(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id, "operation": self.operation, "startEntity": self.start_entity,
            "relations": self.relations, "targetTypes": self.target_types, "maxHops": self.max_hops,
            "aggregate": self.aggregate, "maxRows": self.max_rows,
        }


@dataclass(frozen=True)
class JenaResponse:
    request_id: str
    status: str
    columns: list[str]
    rows: list[list[Any]]
    unit: str
    executed_query: str
    sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    @classmethod
    def from_json(cls, data: dict[str, Any], *, expected_request_id: str | None = None) -> "JenaResponse":
        try:
            request_id = data["requestId"]
            status = data["status"]
            columns = data["columns"]
            rows = data["rows"]
            unit = data["unit"]
        except (KeyError, TypeError) as exc:
            raise WireError(f"응답 필드 누락: {exc}") from exc
        if status not in ALLOWED_STATUS:
            raise WireError(f"알 수 없는 status: {status}")
        if not isinstance(unit, str) or not unit.strip():
            raise WireError("unit이 비어 있습니다")
        if not isinstance(columns, list) or not isinstance(rows, list):
            raise WireError("columns/rows 형식이 올바르지 않습니다")
        if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
            raise WireError("행 너비가 columns와 일치하지 않습니다")
        if expected_request_id is not None and request_id != expected_request_id:
            raise WireError("requestId가 요청과 일치하지 않습니다")
        return cls(
            request_id=request_id, status=status, columns=columns, rows=rows, unit=unit,
            executed_query=data.get("executedQuery", ""), sources=data.get("sources") or [],
            warnings=data.get("warnings") or [], elapsed_ms=int(data.get("elapsedMs") or 0),
        )
