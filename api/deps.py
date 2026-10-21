import re
import hmac
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import AuthConfigurationError, get_signing_key, session_account_binding
from app.db.database import get_db
from app.models.social_account import SocialAccount
from app.models.user import User


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    frontend = urlsplit(settings.FRONTEND_URL)
    allowed = f"{frontend.scheme}://{frontend.netloc}"
    if origin is not None and origin != allowed:
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")


def current_account(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.", headers={"Cache-Control": "no-store"})
    try:
        payload = jwt.decode(token, get_signing_key(), algorithms=[settings.ALGORITHM], options={"require": ["sub", "exp", "binding"]})
        match = re.fullmatch(r"(local|kakao):([1-9][0-9]{0,18})", payload["sub"])
        if not match or int(match[2]) > 2**63 - 1:
            raise ValueError("Invalid subject")
        provider, account_id = match[1], int(match[2])
        account = db.get(User if provider == "local" else SocialAccount, account_id)
        if account is None or (provider == "kakao" and account.provider != "kakao"):
            raise ValueError("Account no longer exists")
        binding = payload["binding"]
        if not isinstance(binding, str) or not re.fullmatch(r"[0-9a-f]{64}", binding):
            raise ValueError("Invalid account binding")
        if not hmac.compare_digest(binding, session_account_binding(provider, account)):
            raise ValueError("Account identity changed")
        return provider, account
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc), headers={"Cache-Control": "no-store"}) from exc
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Authentication required.", headers={"Cache-Control": "no-store"}) from None
