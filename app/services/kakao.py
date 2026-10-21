"""Server-only Kakao authorization-code exchange; tokens are never persisted."""
import httpx

from app.core.config import settings

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"


class KakaoAuthenticationError(RuntimeError):
    pass


class KakaoUnavailable(RuntimeError):
    pass


def _json_object(response: httpx.Response) -> dict:
    if response.status_code >= 500 or response.status_code == 429:
        raise KakaoUnavailable("Kakao service unavailable")
    if response.status_code != 200:
        raise KakaoAuthenticationError("Kakao authentication failed")
    try:
        value = response.json()
    except ValueError as exc:
        raise KakaoAuthenticationError("Invalid Kakao response") from exc
    if not isinstance(value, dict):
        raise KakaoAuthenticationError("Invalid Kakao response")
    return value


async def fetch_kakao_profile(code: str) -> dict:
    form = {"grant_type": "authorization_code", "client_id": settings.KAKAO_REST_API_KEY,
            "redirect_uri": settings.KAKAO_REDIRECT_URI, "code": code}
    if settings.KAKAO_CLIENT_SECRET:
        form["client_secret"] = settings.KAKAO_CLIENT_SECRET
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_data = _json_object(await client.post(TOKEN_URL, data=form))
            token = token_data.get("access_token")
            if not isinstance(token, str) or not token or any(not 33 <= ord(char) <= 126 for char in token):
                raise KakaoAuthenticationError("Missing Kakao access token")
            return _json_object(await client.get(PROFILE_URL, headers={"Authorization": f"Bearer {token}"}))
    except httpx.RequestError as exc:
        raise KakaoUnavailable("Kakao service unavailable") from exc
