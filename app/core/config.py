# 서버 환경설정 : DB접속 및 토큰 시크릿 값 등 환경변수로 설정된 값을 불러오는 파일
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlsplit


def valid_http_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return bool(value and not any(char.isspace() for char in value)
                    and url.scheme in {"http", "https"} and url.hostname
                    and not url.username and not url.password
                    and not url.query and not url.fragment
                    and (url.port is None or 0 < url.port <= 65535))
    except ValueError:
        return False

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    SECRET_KEY      : str = ""
    ALGORITHM       : str = "HS256"
    DATABASE_URL    : str
    FRONTEND_URL: str = "http://localhost:8080"
    COOKIE_SECURE: bool = False
    KAKAO_REST_API_KEY: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = ""

    PORTONE_ENABLED: bool = False
    PORTONE_STORE_ID: str = ""
    PORTONE_CHANNEL_KEY: str = ""
    PORTONE_API_SECRET: str = ""
    PORTONE_WEBHOOK_SECRET: str = ""
    PORTONE_ORDER_FILE: str = "data/portone-orders.json"

    def portone_enabled(self) -> bool:
        import base64
        values = (self.PORTONE_STORE_ID, self.PORTONE_CHANNEL_KEY,
                  self.PORTONE_API_SECRET, self.PORTONE_WEBHOOK_SECRET)
        if not self.PORTONE_ENABLED or not all(value and value == value.strip() for value in values):
            return False
        try:
            secret = self.PORTONE_WEBHOOK_SECRET.removeprefix("whsec_")
            if not base64.b64decode(secret, validate=True):
                return False
        except ValueError:
            return False
        return valid_http_url(self.FRONTEND_URL)

    def kakao_enabled(self) -> bool:
        from app.core.security import AuthConfigurationError, get_signing_key
        try:
            get_signing_key()
        except AuthConfigurationError:
            return False
        return bool(self.KAKAO_REST_API_KEY.strip()
                    and self.KAKAO_REST_API_KEY == self.KAKAO_REST_API_KEY.strip()
                    and valid_http_url(self.KAKAO_REDIRECT_URI)
                    and valid_http_url(self.FRONTEND_URL))

settings = Settings()
