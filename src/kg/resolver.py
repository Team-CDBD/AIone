import re
import unicodedata
from contracts.resolver import Resolution
from .repository import KgRepository

def normalize(text: str) -> str: return " ".join(unicodedata.normalize("NFKC", text).strip().lower().split())

# 한글로 적은 식별자를 원형으로 되돌린다 — '클라이언트A' / '프로덕트 C1'은 Client-A / Product-C1이다.
# 하이픈까지 복원해야 ENTITY_PATTERN이 잡는다(하이픈을 선택적으로 만들면 'products'가 걸린다).
_TRANSLITERATIONS = ((("클라이언트", "클라이안트", "크라이언트"), "Client"),
                     (("프로덕트", "프로덕", "프로독트"), "Product"))
# 4자 미만은 보지 않는다 — '사람들'·'보여줘' 같은 흔한 말이 이름에 걸리는 것을 막는 1차 방어다.
_KOREAN_SPAN = re.compile(r"[가-힣]{4,}")


def transliterate_ids(text: str) -> str:
    for spellings, latin in _TRANSLITERATIONS:
        for spelling in spellings:
            text = re.sub(rf"{spelling}\s*-?\s*([A-Za-z0-9]+)", rf"{latin}-\1", text)
    # 현업 구어체의 "A 고객"은 데이터셋 식별자 Client-A의 흔한 축약이다.
    text = re.sub(r"(?<![A-Za-z0-9])([A-Z])\s*고객(?:사)?", r"Client-\1", text)
    return text
class KgEntityResolver:
    TRGM_THRESHOLD = 0.45
    # 식별자(Client-ZZZ, Product-X9)는 오타 허용 대상이 아니다. 접두사가 같다는 이유만으로
    # trigram 유사도가 0.5~0.7까지 뜨기 때문에, 일반 이름과 같은 임계값을 쓰면 존재하지 않는
    # 개체가 조용히 다른 개체로 치환된다. 식별자 형태 입력은 사실상 정확 일치만 받는다.
    ID_TRGM_THRESHOLD = 0.9
    # Korean particles are Unicode "word" characters, so a trailing \b does not
    # exist in strings such as ``Client-A가``.  Keep the identifier alphabet
    # explicit and stop before any character that cannot belong to an id.
    ENTITY_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(?:Client|Product)-[A-Z0-9]+(?=$|[^A-Za-z0-9_-])", re.I)
    def __init__(self, repo: KgRepository, aliases: dict[str,str] | None = None): self.repo, self.aliases = repo, {normalize(k):v for k,v in (aliases or {}).items()}
    def resolve(self, text: str) -> Resolution:
        value = normalize(text)
        node = self.repo.exact_by_name(value)
        if node: return Resolution(str(node["node_id"]), str(node["name"]), str(node["node_type"]), 1.0, "exact")
        node = self.repo.exact_by_compact_name(value)
        if node: return Resolution(str(node["node_id"]), str(node["name"]), str(node["node_type"]), 1.0, "exact")
        if value in self.aliases:
            node = self.repo.by_id(self.aliases[value])
            if node: return Resolution(str(node["node_id"]),str(node["name"]),str(node["node_type"]),.95,"alias")
        candidates = self.repo.trigram_top(value,3)
        threshold = self.ID_TRGM_THRESHOLD if self.ENTITY_PATTERN.fullmatch(text.strip()) else self.TRGM_THRESHOLD
        if candidates and float(candidates[0].get("sim",0)) >= threshold:
            node=candidates[0]; return Resolution(str(node["node_id"]),str(node["name"]),str(node["node_type"]),float(node["sim"]),"fuzzy")
        return Resolution(None,None,None,0.0,"not_found",[str(row["name"]) for row in candidates])
    # 한글 이름은 ENTITY_PATTERN에 걸리지 않아 오탈자가 있으면 아예 해소되지 않았다.
    # 식별자와 달리 오타 허용 대상이므로 일반 임계값을 쓰되, 길이 제한으로 잡음을 막는다.
    KOREAN_TRGM_THRESHOLD = TRGM_THRESHOLD

    def find_all(self, question: str) -> list[Resolution]:
        text = transliterate_ids(question)
        spans = [m.group(0) for m in self.ENTITY_PATTERN.finditer(text)]
        found = [self.resolve(span) for span in spans]
        seen = {item.node_id for item in found if item.node_id}
        # 해소에 실패한 식별자. 이 안에 들어 있는 짧은 이름을 부분 문자열로 다시 주워오면
        # Client-ZZZ 질문이 Client-Z 답으로 조용히 바뀐다 — 식별자 보호를 우회하는 경로였다.
        unresolved = [normalize(span) for span, item in zip(spans, found) if item.node_id is None]
        for node in self.repo.names_in_text(text):
            node_id, name = str(node["node_id"]), str(node["name"])
            if node_id in seen: continue
            if any(normalize(name) in span for span in unresolved): continue
            found.append(Resolution(node_id,name,str(node["node_type"]),1.0,"exact")); seen.add(node_id)
        if not seen: found.extend(self._fuzzy_korean(text, seen))
        return found

    def _fuzzy_korean(self, text: str, seen: set) -> list[Resolution]:
        """정확 일치가 하나도 없을 때만 한글 토큰을 오타 허용으로 다시 본다."""
        extra = []
        for token in dict.fromkeys(_KOREAN_SPAN.findall(text)):
            candidates = self.repo.trigram_top(normalize(token), 1)
            if not candidates: continue
            best = candidates[0]
            if float(best.get("sim", 0)) < self.KOREAN_TRGM_THRESHOLD: continue
            node_id = str(best["node_id"])
            if node_id in seen: continue
            extra.append(Resolution(node_id,str(best["name"]),str(best["node_type"]),float(best["sim"]),"fuzzy")); seen.add(node_id)
        return extra
