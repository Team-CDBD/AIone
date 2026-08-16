from dataclasses import asdict
from contracts.tool import ToolResult

TACC_PROFILES = {
    "structured_aggregate": {"K", "A"},
    "document_semantic": {"K", "A", "G"},
    "relation_traversal": {"K", "A"},
    "fallback_ambiguous": {"K", "A", "D", "G"},
}
DEFAULT_PROFILE = "fallback_ambiguous"


def compose_context(result: ToolResult, profile_name: str, guideline: str = "") -> str:
    """모듈별 지침(G)은 ModuleSpec이 들고 오므로 여기서 툴 이름을 알 필요가 없다."""
    profile = TACC_PROFILES.get(profile_name, TACC_PROFILES[DEFAULT_PROFILE]); parts = []
    if "K" in profile: parts.append(f"[K] columns={result.answer_basis.columns}\nrows={result.answer_basis.rows}\nunit={result.answer_basis.unit}")
    if "A" in profile: parts.append(f"[A] {', '.join(str(a.tool) + ': ' + a.reason for a in result.candidate_actions) or 'none'}")
    if "D" in profile: parts.append(f"[D] {asdict(result.provenance)}")
    if "G" in profile and guideline: parts.append(f"[G] {guideline}")
    return "\n\n".join(parts)
