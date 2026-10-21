"""Kakao browser login with a signed, expiring nonce cookie."""
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings, valid_http_url
from app.core.security import AuthConfigurationError, create_session_token, get_signing_key, session_account_binding, set_session_cookie
from app.db.database import get_db
from app.models.social_account import SocialAccount
from app.services.kakao import AUTHORIZE_URL, KakaoAuthenticationError, KakaoUnavailable, fetch_kakao_profile

router = APIRouter(prefix="/auth/kakao", tags=["auth"])
STATE_COOKIE = "kakao_oauth_state"
STATE_SECONDS = 600


def _finish(error: str | None = None) -> RedirectResponse:
    # Invalid deployment settings must never turn a callback into an open redirect.
    root = settings.FRONTEND_URL if valid_http_url(settings.FRONTEND_URL) else "http://localhost:8080"
    target = root.rstrip("/") + "/"
    if error:
        target += "?" + urlencode({"auth_error": error})
    response = RedirectResponse(target, status_code=303, headers={"Cache-Control": "no-store"})
    response.delete_cookie(STATE_COOKIE, path="/", httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")
    return response


def _valid_state(request: Request, nonce: str | None) -> bool:
    if not nonce:
        return False
    try:
        claims = jwt.decode(request.cookies.get(STATE_COOKIE, ""), get_signing_key(),
                            algorithms=[settings.ALGORITHM], options={"require": ["exp", "nonce", "purpose"]})
        stored = claims["nonce"]
        return (claims["purpose"] == STATE_COOKIE and isinstance(stored, str)
                and hmac.compare_digest(stored.encode("utf-8"), nonce.encode("utf-8")))
    except (jwt.InvalidTokenError, AuthConfigurationError, ValueError, TypeError):
        return False


def get_or_create_account(db: Session, profile: dict) -> SocialAccount:
    if not isinstance(profile, dict) or type(profile.get("id")) is not int or not 0 < profile["id"] <= 2**63 - 1:
        raise KakaoAuthenticationError("Invalid Kakao member ID")
    details = profile.get("kakao_account", {})
    if not isinstance(details, dict) or not isinstance(details.get("profile", {}), dict):
        raise KakaoAuthenticationError("Invalid Kakao profile")
    nickname = details.get("profile", {}).get("nickname")
    nickname = nickname.strip()[:255] if isinstance(nickname, str) else ""
    email = details.get("email")
    email = email.strip() if isinstance(email, str) and len(email.strip()) <= 320 else None
    email = email or None
    member_id = str(profile["id"])
    query = select(SocialAccount).where(SocialAccount.provider == "kakao", SocialAccount.provider_user_id == member_id)
    account = db.scalar(query)
    if account is not None:
        return account
    account = SocialAccount(provider="kakao", provider_user_id=member_id,
                            display_name=nickname or "카카오 사용자", email=email)
    db.add(account)
    try:
        db.commit()
        db.refresh(account)
        return account
    except IntegrityError:
        db.rollback()
        account = db.scalar(query)
        if account is None:
            raise
        return account


@router.get("/login")
def login():
    if not settings.kakao_enabled():
        raise HTTPException(status_code=503, detail="Kakao login is unavailable", headers={"Cache-Control": "no-store"})
    nonce = secrets.token_urlsafe(32)
    state_cookie = jwt.encode({"purpose": STATE_COOKIE, "nonce": nonce,
                               "exp": datetime.now(timezone.utc) + timedelta(seconds=STATE_SECONDS)},
                              get_signing_key(), algorithm=settings.ALGORITHM)
    url = AUTHORIZE_URL + "?" + urlencode({"response_type": "code", "client_id": settings.KAKAO_REST_API_KEY,
                                          "redirect_uri": settings.KAKAO_REDIRECT_URI, "state": nonce,
                                          "prompt": "login"})
    response = RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
    response.set_cookie(STATE_COOKIE, state_cookie, max_age=STATE_SECONDS, path="/", httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax")
    return response


@router.get("/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None,
                   error: str | None = None, db: Session = Depends(get_db)):
    if not settings.kakao_enabled():
        return _finish("kakao_unavailable")
    if not _valid_state(request, state):
        return _finish("invalid_state")
    if error:
        return _finish("kakao_cancelled" if error == "access_denied" else "kakao_failed")
    if not code:
        return _finish("kakao_failed")
    try:
        profile = await fetch_kakao_profile(code)
        account = get_or_create_account(db, profile)
        token = create_session_token("kakao", account.id, session_account_binding("kakao", account))
    except (KakaoUnavailable, AuthConfigurationError):
        return _finish("kakao_unavailable")
    except (KakaoAuthenticationError, SQLAlchemyError):
        db.rollback()
        return _finish("kakao_failed")
    response = _finish()
    set_session_cookie(response, token)
    return response
