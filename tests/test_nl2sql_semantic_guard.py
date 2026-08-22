from contracts.tool import ToolStatus
from nl2sql.domain.semantic_guard import check
from nl2sql.repository import SqlRepository
from nl2sql.service import SqlService
from .fakes import FakeDb, FakeLlm

# --- 긍정 오라클: 용어 기준 컬럼을 그대로 쓰는 SQL은 통과해야 한다 ---

def test_매출_기준_컬럼_사용시_통과():
    result = check("2024년 1분기 매출액은 얼마야?", "SELECT SUM(amount) FROM sales WHERE quarter = '2024-Q1'")
    assert result.ok

def test_계약금액_기준_컬럼_사용시_통과():
    result = check("이 고객의 계약금액 합계는?", "SELECT SUM(amount) FROM contracts WHERE client_id = 'c1'")
    assert result.ok

def test_연봉_기준_컬럼_사용시_통과():
    result = check("직원들의 연봉 평균은?", "SELECT AVG(salary) FROM employees")
    assert result.ok

def test_매출_건수_질문은_count로도_통과():
    result = check("이번 분기 매출 건수는 몇 건이야?", "SELECT COUNT(*) FROM sales WHERE quarter = '2024-Q1'")
    assert result.ok

def test_용어가_없는_질문은_무조건_통과():
    result = check("고객 목록을 보여줘", "SELECT id, name FROM clients")
    assert result.ok

def test_고객사_count는_name_join을_요구하지_않음():
    assert check("2024년에 등록된 고객사는 몇 개야?", "SELECT COUNT(id) FROM clients").ok

# --- 부정 오라클: 규칙별로 하나씩 ---

def test_매출_질문에_계약금액_컬럼_쓰면_거부():
    result = check("올해 매출액은 얼마야?", "SELECT SUM(amount) FROM contracts")
    assert not result.ok
    assert "매출" in (result.reason or "")

def test_계약금액_질문에_매출_컬럼_쓰면_거부():
    result = check("이 계약의 계약금액은?", "SELECT SUM(amount) FROM sales")
    assert not result.ok
    assert "계약금액" in (result.reason or "")

def test_연봉_질문에_매출_컬럼_쓰면_거부():
    result = check("김철수의 연봉은 얼마야?", "SELECT amount FROM sales WHERE client_id = 'x'")
    assert not result.ok
    assert "연봉" in (result.reason or "")

def test_불완전한_분기값_필터는_거부():
    result = check("2024년 매출액은?", "SELECT SUM(amount) FROM sales WHERE quarter = '2024-Q*'")
    assert not result.ok
    assert "quarter" in (result.reason or "") or "날짜" in (result.reason or "")

def test_기준_컬럼이_전혀_없으면_거부():
    result = check("올해 매출액은 얼마야?", "SELECT COUNT(*) FROM clients")
    assert not result.ok

def test_제품별_질문은_제품명_join을_요구():
    assert not check("제품별 총 계약 금액", "SELECT product_id, SUM(amount) FROM contracts GROUP BY product_id").ok
    assert check("제품별 총 계약 금액", "SELECT p.name, SUM(c.amount) FROM contracts c JOIN products p ON p.id=c.product_id GROUP BY p.name").ok

def test_최고_연봉_부서는_부서명을_요구():
    assert not check("평균 연봉이 가장 높은 부서는 어디야?", "SELECT dept_id, AVG(salary) FROM employees GROUP BY dept_id").ok
    assert check("평균 연봉이 가장 높은 부서는 어디야?", "SELECT d.name, AVG(e.salary) FROM employees e JOIN departments d ON d.id=e.dept_id GROUP BY d.name").ok

# --- SqlService 통합: 의미 오류 거부 시 append_correction 재시도 경로를 탄다 ---

def test_service_semantic_rejection_triggers_single_retry():
    llm = FakeLlm(["SELECT SUM(amount) FROM contracts", "SELECT SUM(amount) FROM sales WHERE quarter = '2024-Q1'"])
    db = FakeDb([{"sum": 100}])
    outcome = SqlService(SqlRepository(db), llm).answer("2024년 1분기 매출액은 얼마야?", [], 100)
    assert outcome.status == ToolStatus.OK
    assert outcome.sql == "SELECT SUM(amount) FROM sales WHERE quarter = '2024-Q1' LIMIT 100"

def test_service_semantic_rejection_exhausts_retry_and_reports_reason():
    llm = FakeLlm(["SELECT SUM(amount) FROM contracts", "SELECT SUM(amount) FROM contracts"])
    db = FakeDb([{"sum": 100}])
    outcome = SqlService(SqlRepository(db), llm).answer("2024년 1분기 매출액은 얼마야?", [], 100)
    assert outcome.status == ToolStatus.GUARD_REJECTED
    assert "매출" in (outcome.reason or "")

# --- evaluate_nl2sql_extended.rows_match: 순수 채점 함수 단위 테스트 ---

def test_rows_match_pure_scoring_function():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from evaluate_nl2sql_extended import rows_match

    assert rows_match([[1, "a"]], [[1, "a"]])
    assert not rows_match([[1, "a"]], [[1, "b"]])
    assert rows_match([[1], [2]], [[2], [1]], ordered=False)
    assert not rows_match([[1], [2]], [[2], [1]], ordered=True)
