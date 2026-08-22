from __future__ import annotations
from dataclasses import dataclass
import re

# products/contracts/employees/sales 컬럼 — src/nl2sql/domain/schema_card.py와 동기화된 부분집합
SCHEMA_COLUMNS = {
    "departments": {"id", "name", "head_id"},
    "products": {"id", "name", "category", "price_monthly", "status"},
    "contracts": {"id", "client_id", "product_id", "manager_id", "contract_type", "amount", "status"},
    "employees": {"id", "name", "dept_id", "salary"},
    "clients": {"id", "name", "industry", "region", "company_size", "registered_at"},
    "projects": {"id", "name", "client_id", "manager_id", "contract_id", "status", "budget"},
    "sales": {"id", "contract_id", "client_id", "product_id", "amount", "sale_date", "quarter", "category", "region"},
    "support_tickets": {"id", "client_id", "product_id", "assignee_id", "priority", "status", "created_at", "resolved_at"},
}

@dataclass(frozen=True)
class SemanticGuardResult:
    ok: bool
    reason: str | None = None

@dataclass(frozen=True)
class ColumnMapping:
    name: str
    aliases: tuple[str, ...]
    canonical_column: str
    forbidden_columns: tuple[str, ...] = ()

# schema_card의 매출/계약금액/연봉 용어를 코드가 검증 가능한 형태로 옮긴다.
COLUMN_MAPPINGS = (
    ColumnMapping("매출", ("매출", "매출액"), "sales.amount", ("products.price_monthly", "contracts.amount")),
    ColumnMapping("계약금액", ("계약금액", "계약 금액"), "contracts.amount", ("sales.amount", "products.price_monthly")),
    ColumnMapping("연봉", ("연봉",), "employees.salary", ("sales.amount", "contracts.amount", "products.price_monthly")),
)

_TABLE_REF_RE = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?", re.IGNORECASE)
_QUALIFIED_COLUMN_RE = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"\b[a-z_][a-z0-9_]*\b", re.IGNORECASE)
_SQL_KEYWORDS = {"select","from","join","where","group","by","order","limit","on","as","and","or","sum","avg","count","desc","asc"}

def check(question: str, sql: str) -> SemanticGuardResult:
    if re.search(r"\bquarter\s*=\s*'\d{4}-q(?:\*|)'", sql, re.IGNORECASE):
        return SemanticGuardResult(False, "의미 오류: 연도 전체를 불완전한 quarter 값으로 필터링할 수 없습니다. 날짜 범위를 사용하세요.")
    ctx = _SqlContext(sql)
    if ("고객사" in question and not any(term in question for term in ("몇 개", "개수", "수는"))
            and any(term in question for term in ("알려", "어디", "가장"))
            and not ctx.uses_column("clients.name")):
        return SemanticGuardResult(False, "의미 오류: 표시값 질문은 id 대신 clients.name을 JOIN해 반환해야 합니다.")
    display_rules = (
        (("제품별", "제품 목록", "제품은"), "products.name"),
        (("부서는 어디", "부서 어디", "가장 높은 부서"), "departments.name"),
    )
    for terms, column in display_rules:
        if any(term in question for term in terms) and not ctx.uses_column(column):
            return SemanticGuardResult(False, f"의미 오류: 표시값 질문은 id 대신 {column}을 JOIN해 반환해야 합니다.")
    matched = [m for m in COLUMN_MAPPINGS if any(alias in question for alias in m.aliases)]
    if not matched: return SemanticGuardResult(True)
    for mapping in matched:
        for forbidden in mapping.forbidden_columns:
            if ctx.uses_column(forbidden): return SemanticGuardResult(False, _error(mapping, f"{forbidden}는 해당 용어의 기준 컬럼이 아닙니다."))
        revenue_count = (mapping.name == "매출" and any(term in question for term in ("건수", "몇 건", "개수"))
                         and "sales" in ctx.tables and "count" in ctx.identifiers)
        if not revenue_count and not ctx.uses_column(mapping.canonical_column):
            return SemanticGuardResult(False, _error(mapping, "생성 SQL에 기준 컬럼이 없습니다."))
    return SemanticGuardResult(True)

def _error(mapping: ColumnMapping, detail: str) -> str:
    return f"의미 오류: '{mapping.name}'은 {mapping.canonical_column} 기준으로 해석해야 합니다. {detail}"

class _SqlContext:
    def __init__(self, sql: str) -> None:
        self.sql = sql.lower()
        self.alias_to_table = self._extract_aliases()
        self.tables = set(self.alias_to_table.values())
        self.qualified_columns = self._extract_qualified_columns()
        self.identifiers = set(_IDENTIFIER_RE.findall(self.sql))

    def uses_column(self, canonical_column: str) -> bool:
        table, column = canonical_column.lower().split(".", 1)
        if canonical_column.lower() in self.qualified_columns: return True
        if table not in self.tables or column not in self.identifiers: return False
        candidates = [t for t in self.tables if column in SCHEMA_COLUMNS.get(t, set())]
        return set(candidates) == {table}

    def _extract_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for table, alias in _TABLE_REF_RE.findall(self.sql):
            table = table.lower()
            if table not in SCHEMA_COLUMNS: continue
            aliases[table] = table
            if alias and alias.lower() not in _SQL_KEYWORDS: aliases[alias.lower()] = table
        return aliases

    def _extract_qualified_columns(self) -> set[str]:
        columns = set()
        for qualifier, column in _QUALIFIED_COLUMN_RE.findall(self.sql):
            table = self.alias_to_table.get(qualifier.lower())
            if table and column.lower() in SCHEMA_COLUMNS.get(table, set()): columns.add(f"{table}.{column.lower()}")
        return columns
