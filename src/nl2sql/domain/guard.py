from __future__ import annotations
from dataclasses import dataclass
import json
import re
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

ALLOWED_TABLES = {"departments","employees","clients","products","contracts","projects","sales","support_tickets"}
BANNED = {"insert","update","delete","drop","alter","create","truncate","grant","revoke","copy","vacuum","call","do","merge","pg_read_file","pg_sleep","dblink","lo_import","strftime","set","reset"}

@dataclass(frozen=True)
class GuardResult:
    ok: bool
    sql: str | None = None
    reason: str | None = None

def extract_sql(raw: str) -> str:
    value = raw.strip()
    # The preferred model contract is {"sql":"SELECT ..."}.  Refuse other
    # JSON shapes instead of accidentally treating arbitrary JSON as SQL.
    if value.startswith("{"):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(payload, dict) and set(payload) == {"sql"} and isinstance(payload["sql"], str):
            value = payload["sql"].strip()
        else:
            return value
    if "```" in value and value.count("```") != 2: return value
    match = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, re.I | re.S)
    if match: return match.group(1).strip()
    # Models often add one short explanation before a fenced query.  Extract
    # exactly one SQL fence; multiple fences remain rejected by the guard.
    fences = re.findall(r"```(?:sql)?\s*(.*?)\s*```", value, re.I | re.S)
    return fences[0].strip() if len(fences) == 1 else value

def strip_code_fence(raw: str) -> str: return extract_sql(raw)

def guard(raw: str, max_rows: int = 100) -> GuardResult:
    if not isinstance(raw, str): return GuardResult(False, reason="SQL 문자열이 아닙니다")
    sql = extract_sql(raw)
    if "--" in sql or "/*" in sql: return GuardResult(False, reason="주석 포함")
    without_trailing = sql.rstrip().removesuffix(";").strip()
    if ";" in without_trailing: return GuardResult(False, reason="단일 SELECT 문만 허용")
    if not re.match(r"(?is)^\s*(?:with\s+[\w\s,()]+\s+as\s*\([^;]+\)\s*)?select\b", without_trailing):
        return GuardResult(False, reason="SELECT 이외 구문")
    low = without_trailing.lower()
    if any(re.search(rf"\b{re.escape(word)}\b", low) for word in BANNED): return GuardResult(False, reason="금지 키워드")
    try:
        parsed = parse_one(without_trailing, read="postgres")
    except ParseError as exc:
        return GuardResult(False, reason=f"SQL 파싱 실패: {exc}")
    cte_names = {cte.alias_or_name.lower() for cte in parsed.find_all(exp.CTE)}
    tables = {table.name.lower() for table in parsed.find_all(exp.Table)
              if table.name and table.name.lower() not in cte_names}
    for name in tables:
        if name not in ALLOWED_TABLES: return GuardResult(False, reason=f"허용되지 않은 테이블: {name}")
    if not tables: return GuardResult(False, reason="허용 테이블이 없습니다")
    limit = max(1, min(int(max_rows), 1000))
    match = re.search(r"(?i)\blimit\s+(\d+)\s*$", without_trailing)
    if match:
        if int(match.group(1)) > limit: without_trailing = without_trailing[:match.start()] + f"LIMIT {limit}"
    else: without_trailing += f" LIMIT {limit}"
    return GuardResult(True, without_trailing)

def infer_unit(sql: str) -> str:
    low = sql.lower()
    if "sum(" in low and "amount" in low: return "매출액 합계(만원)"
    if "support_tickets" in low and "count(" in low: return "티켓 건수"
    if "count(" in low: return "행 개수"
    if "avg(" in low: return "평균값"
    return "조회 행"

def extract_limit(question: str) -> int | None:
    match = re.search(r"(?:상위|최대)\s*(\d+)|\btop\s*(\d+)", question, re.I)
    return int(next(group for group in match.groups() if group)) if match else None
