from .schema_card import SCHEMA_CARD
def build_prompt(question: str, hint_tables: list[str]) -> str:
    hints = ", ".join(hint_tables) if hint_tables else "없음"
    return (f"{SCHEMA_CARD}\n힌트 테이블: {hints}\n"
            "값 예시: quarter='2025-Q3', category='security', status='active'.\n"
            "고객사/제품/부서가 무엇인지 묻는 경우 id가 아니라 해당 테이블의 name을 JOIN해 반환하세요.\n"
            f"질문: {question}\n설명·마크다운 없이 단일 SELECT SQL만 출력:")
def append_correction(prompt: str, rejected: str, reason: str) -> str:
    """거부된 SQL을 반드시 함께 보여준다 — temperature=0에서 무엇이 틀렸는지 모르는 재시도는
    같은 문장을 그대로 다시 만들어낼 뿐이다."""
    return (f"{prompt}\n직전 출력: {rejected.strip()}\n거부 사유: {reason}\n"
            "위 스키마에 없는 열은 쓰지 말고, 지적된 부분을 고쳐 단일 SELECT SQL만 다시 출력:")
