import httpx
from contracts.infra import LlmBadRequest,LlmError,LlmTimeout
class OllamaClient:
    EMBED_DIM=768
    EMBED_TIMEOUT_S=30
    # 은닉 추론을 끄면 SQL 한 건이 30초대에서 2~3초로 떨어진다(실측). 90초는 그 뒤에 남기는 안전망일 뿐
    # 정상 경로의 예산이 아니다.
    GENERATE_TIMEOUT_S=90
    # 기본 5m이면 문항 사이 유휴에 모델이 내려가 재로드(실측 11.5초)가 매번 붙는다.
    KEEP_ALIVE="30m"
    def __init__(self,base_url:str,generate_model:str="gemma4:e2b",embed_model:str="nomic-embed-text"):
        self.base_url,self.generate_model,self.embed_model=base_url.rstrip("/"),generate_model,embed_model
        self._http=httpx.Client(base_url=self.base_url,timeout=self.GENERATE_TIMEOUT_S)
        self._supports_think=True  # think를 모르는 서버/모델을 만나면 한 번 겪고 끈다
    def _post(self,path:str,payload:dict,timeout_s:float):
        try:
            response=self._http.post(path,json=payload,timeout=timeout_s);response.raise_for_status();return response.json()
        except httpx.HTTPStatusError as exc:
            raise LlmBadRequest(str(exc)) if exc.response.status_code==400 else LlmError(str(exc)) from exc
        # httpx.TimeoutException은 TimeoutError가 아니다 — 예전 `except TimeoutError`는 한 번도 걸리지 않아
        # 시간 초과가 전부 UPSTREAM_ERROR로 보고됐다.
        except httpx.TimeoutException as exc:raise LlmTimeout(f"{path} {timeout_s}초 초과") from exc
        except Exception as exc:raise LlmError(str(exc)) from exc
    def embed(self,text:str,*,kind:str):
        prefix="search_document: " if kind=="document" else "search_query: "
        payload={"model":self.embed_model,"input":prefix+text,"keep_alive":self.KEEP_ALIVE}
        vector=self._post("/api/embed",payload,self.EMBED_TIMEOUT_S)["embeddings"][0]
        if len(vector)!=self.EMBED_DIM:raise LlmError(f"embedding dimension {len(vector)} != {self.EMBED_DIM}")
        return vector
    def generate(self,prompt:str,*,stop=None,max_tokens=300,timeout_s=None):
        budget=self.GENERATE_TIMEOUT_S if timeout_s is None else timeout_s
        payload={"model":self.generate_model,"prompt":prompt,"stream":False,"keep_alive":self.KEEP_ALIVE,
                 "options":{"temperature":0,"num_predict":max_tokens,"stop":stop or []}}
        if self._supports_think:
            # think를 모르는 서버는 400으로 답한다. 그 경우에만 추론 포함 경로로 되돌린다 —
            # 일시적 장애로 이 최적화를 영구히 꺼버리지 않기 위해서다.
            try:return self._post("/api/generate",dict(payload,think=False),budget)["response"].strip()
            except LlmBadRequest:self._supports_think=False
        return self._post("/api/generate",payload,budget)["response"].strip()
    def close(self):self._http.close()
