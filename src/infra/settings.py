from dataclasses import dataclass
import os
@dataclass(frozen=True)
class Settings:
    TOP_K:int=5
    TAU:float=.55
    # 자격증명을 기본값으로 두지 않는다 — 코드에 박힌 비밀번호는 저장소에 그대로 커밋된다.
    PG_DSN:str=""
    # 접속 프로필 저장소. 앱이 다른 서버로 갈아타도 프로필 자체는 이 DSN이 가리키는 곳에 남는다.
    CONFIG_PG_DSN:str=""
    # 프로필 비밀번호 암호화 키. DB와 분리해 보관하며 Fernet URL-safe base64 형식이다.
    PROFILE_ENCRYPTION_KEY:str=""
    OLLAMA_URL:str=""
    GENERATE_MODEL:str="gemma4:e4b"
    EMBED_MODEL:str="nomic-embed-text:latest"
    KG_ENGINE:str="python"  # python|jena|shadow. 이번 라운드는 python 고정 운영, jena는 배선만.
    @classmethod
    def from_env(cls):
        return cls(
            TOP_K=int(os.getenv("TOP_K","5")),
            TAU=float(os.getenv("TAU",".55")),
            PG_DSN=os.getenv("PG_DSN",cls.PG_DSN),
            CONFIG_PG_DSN=os.getenv("CONFIG_PG_DSN",cls.CONFIG_PG_DSN),
            PROFILE_ENCRYPTION_KEY=os.getenv("PROFILE_ENCRYPTION_KEY",cls.PROFILE_ENCRYPTION_KEY),
            OLLAMA_URL=os.getenv("OLLAMA_URL",cls.OLLAMA_URL),
            GENERATE_MODEL=os.getenv("GENERATE_MODEL",cls.GENERATE_MODEL),
            EMBED_MODEL=os.getenv("EMBED_MODEL",cls.EMBED_MODEL),
            KG_ENGINE=os.getenv("KG_ENGINE",cls.KG_ENGINE),
        )
