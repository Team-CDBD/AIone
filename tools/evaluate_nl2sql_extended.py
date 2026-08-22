"""확장 NL2SQL 픽스처(tests/fixtures/nl2sql_extended_questions.json)를 실 인프라(Db/Llm)에 대해
실행하고, 생성 SQL 실행 결과를 기대 SQL 실행 결과와 비교(EX: execution-match)한다.

CLI 진입점은 실제 PostgresDb/OllamaClient가 필요하므로 이 환경(FakeDb/FakeLlm만 있는 테스트 러너)에서는
직접 실행할 수 없다 — 채점 로직(rows_match)만 순수 함수로 분리해 단위 테스트 가능하게 한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "nl2sql_extended_questions.json"
DEFAULT_OUTPUT = ROOT / "tests" / "results" / "nl2sql_extended_results.jsonl"
sys.path.insert(0, str(ROOT / "src"))

from contracts.infra import Db, Llm  # noqa: E402
from contracts.tool import ToolStatus  # noqa: E402
from nl2sql.adapter import Nl2SqlTool  # noqa: E402
from nl2sql.repository import SqlRepository  # noqa: E402
from nl2sql.service import SqlService  # noqa: E402


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, (date, datetime)): return value.isoformat()
    return value


def _normalized_rows(rows: list[list[Any]], ordered: bool) -> list[tuple[Any, ...]]:
    normalized = [tuple(_normalize_cell(v) for v in row) for row in rows]
    return normalized if ordered else sorted(normalized, key=repr)


def rows_match(expected_rows: list[list[Any]], actual_rows: list[list[Any]], ordered: bool = False) -> bool:
    """순수 함수 — DB/LLM 없이 단위 테스트 가능한 실행 결과 일치(EX) 판정."""
    return _normalized_rows(expected_rows, ordered) == _normalized_rows(actual_rows, ordered)


def is_empty_result(rows: list[list[Any]]) -> bool:
    return (
        not rows
        or all(all(value is None for value in row) for row in rows)
        or (len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] == 0)
    )


def _load_completed(path: Path) -> dict[str, dict]:
    if not path.exists(): return {}
    completed = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            completed[item["id"]] = item
    return completed


def evaluate_case(case: dict, db: Db, tool: Nl2SqlTool) -> dict:
    expected_sql = case["expected_sql"].rstrip().removesuffix(";")
    try:
        expected_rows = db.fetch(expected_sql)
    except Exception as exc:  # noqa: BLE001 — 픽스처 실행 오류는 결과로만 기록한다
        return _record(case, "fixture_error", None, str(exc))

    result = tool.run(question=case["q"])
    if result.status not in (ToolStatus.OK, ToolStatus.EMPTY):
        return _record(case, "generation_error", result.provenance.query, "; ".join(result.notes) or result.status.value)

    ordered = "order by" in case["expected_sql"].lower()
    same = rows_match(list(expected_rows), result.answer_basis.rows, ordered)
    if same and is_empty_result(list(expected_rows)):
        status = "empty_result_unscored"
    else:
        status = "pass" if same else "wrong_result"
    return _record(case, status, result.provenance.query, None)


def _record(case: dict, status: str, generated_sql: str | None, error: str | None) -> dict:
    return {
        "id": case["id"], "q": case["q"], "focus": case["focus"], "tags": case["tags"],
        "status": status, "generated_sql": generated_sql, "expected_sql": case["expected_sql"], "error": error,
    }


def run_fixture(db: Db, llm: Llm, output: Path, limit: int | None = None, fresh: bool = False) -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if limit is not None: cases = cases[:limit]
    output.parent.mkdir(parents=True, exist_ok=True)
    if fresh: output.unlink(missing_ok=True)
    completed = _load_completed(output)

    tool = Nl2SqlTool(SqlService(SqlRepository(db), llm))
    for index, case in enumerate(cases, start=1):
        if case["id"] in completed: continue
        record = evaluate_case(case, db, tool)
        with output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        completed[case["id"]] = record
        counts = Counter(item["status"] for item in completed.values())
        print(f"[{index}/{len(cases)}] {case['id']} {record['status']} | {dict(counts)}", flush=True)

    selected = [completed[case["id"]] for case in cases]
    counts = Counter(item["status"] for item in selected)
    print(f"done: total={len(selected)} {dict(counts)}")
    print(f"results: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    # 실 인프라 구성 — 이 환경에는 없으므로 여기서만 지연 import한다.
    from infra.settings import Settings  # noqa: E402
    from infra.db import PostgresDb  # noqa: E402
    from infra.llm import OllamaClient  # noqa: E402

    settings = Settings.from_env()
    db = PostgresDb(settings.PG_DSN)
    llm = OllamaClient(settings.OLLAMA_URL, settings.GENERATE_MODEL, settings.EMBED_MODEL)
    run_fixture(db, llm, args.output, args.limit, args.fresh)


if __name__ == "__main__":
    main()
