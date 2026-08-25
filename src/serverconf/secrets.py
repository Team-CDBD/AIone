"""접속 프로필 비밀번호의 저장 암호화.

키는 DB와 분리된 환경변수가 소유한다. 접두사가 없는 값은 기존 배포의 평문으로 간주해
읽을 수 있게 하되, repository의 마이그레이션이 즉시 암호문으로 다시 저장한다.
"""
from cryptography.fernet import Fernet, InvalidToken

PREFIX = "enc:v1:"


class SecretKeyInvalid(ValueError): pass


class PasswordCipher:
    def __init__(self, key: str):
        if not key: raise SecretKeyInvalid("PROFILE_ENCRYPTION_KEY가 설정되지 않았습니다")
        try: self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise SecretKeyInvalid("PROFILE_ENCRYPTION_KEY 형식이 올바르지 않습니다") from exc

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext in (None, ""): return plaintext
        if plaintext.startswith(PREFIX): return plaintext
        return PREFIX + self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, stored: str | None) -> str:
        if not stored: return ""
        if not stored.startswith(PREFIX): return stored  # 기존 평문: migrate_plaintext_passwords가 회전한다.
        try: return self._fernet.decrypt(stored[len(PREFIX):].encode()).decode()
        except InvalidToken as exc: raise SecretKeyInvalid("저장된 프로필 비밀번호를 복호화할 수 없습니다") from exc

    @staticmethod
    def needs_migration(stored: str | None) -> bool: return bool(stored) and not stored.startswith(PREFIX)
