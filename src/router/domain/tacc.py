from dataclasses import asdict
from contracts.tool import ToolResult

# G(모듈 지침)를 빼면 모듈이 들고 온 지침이 모델에 도달하지 않는다 — 실제로 KG 답변이
# 근거 표를 두고도 "없습니다"로 나오던 원인이었다.
TACC_PROFILES = {
    "structured_aggregate": {"K", "A", "G"},
    "document_semantic": {"K", "A", "G"},
    "relation_traversal": {"K", "A", "G"},
    "fallback_ambiguous": {"K", "A", "D", "G"},
}
DEFAULT_PROFILE = "fallback_ambiguous"


def _table(result: ToolResult) -> str:
    """파이썬 repr(`rows=[[...]]`)을 그대로 넘기면 모델이 행을 읽지 못한다. 표로 편다."""
    basis = result.answer_basis
    header = f"[K] 조회 결과 {basis.row_count}건 (단위: {basis.unit})"
    if not basis.rows: return f"{header}\n(행 없음)"
    columns = " | ".join(basis.columns)
    divider = " | ".join("---" for _ in basis.columns)
    body = "\n".join(" | ".join("" if value is None else str(value) for value in row) for row in basis.rows)
    return f"{header}\n{columns}\n{divider}\n{body}"


def compose_context(result: ToolResult, profile_name: str, guideline: str = "") -> str:
    """모듈별 지침(G)은 ModuleSpec이 들고 오므로 여기서 툴 이름을 알 필요가 없다."""
    profile = TACC_PROFILES.get(profile_name, TACC_PROFILES[DEFAULT_PROFILE]); parts = []
    if "K" in profile: parts.append(_table(result))
    # 빈 섹션은 넣지 않는다 — "[A] none"이 근거가 없다는 신호로 읽혀 답변을 오염시켰다.
    if "A" in profile and result.candidate_actions:
        parts.append("[A] " + ", ".join(f"{a.tool}: {a.reason}" for a in result.candidate_actions))
    if "D" in profile: parts.append(f"[D] {asdict(result.provenance)}")
    if "G" in profile and guideline: parts.append(f"[G] {guideline}")
    return "\n\n".join(parts)
