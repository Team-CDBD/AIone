import re
import unicodedata
from contracts.resolver import Resolution
from .repository import KgRepository

def normalize(text: str) -> str: return " ".join(unicodedata.normalize("NFKC", text).strip().lower().split())
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
    def find_all(self, question: str) -> list[Resolution]:
        found = [self.resolve(m.group(0)) for m in self.ENTITY_PATTERN.finditer(question)]
        seen = {item.node_id for item in found if item.node_id}
        for node in self.repo.names_in_text(question):
            node_id = str(node["node_id"])
            if node_id not in seen:
                found.append(Resolution(node_id,str(node["name"]),str(node["node_type"]),1.0,"exact")); seen.add(node_id)
        return found
