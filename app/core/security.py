"""Password hashing and shared browser session primitives."""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response

from app.core.config import settings

SESSION_SECONDS = 1800
_OLD_DEFAULT_KEY = "my-secret-key-for-jwk-must-be-32-bytes-or-more"
_HASH_PREFIX = "scrypt$16384$8$1$"


class AuthConfigurationError(RuntimeError):
    pass


def get_signing_key() -> str:
    key = settings.SECRET_KEY
    if not key.strip() or key == _OLD_DEFAULT_KEY or len(key.encode("utf-8")) < 32:
        raise AuthConfigurationError("Configure SECRET_KEY with a new secret of at least 32 bytes.")
    if settings.ALGORITHM not in {"HS256", "HS384", "HS512"}:
        raise AuthConfigurationError("Configure a supported HMAC JWT algorithm.")
    return key


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=64)
    return f"{_HASH_PREFIX}{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not isinstance(stored, str) or not isinstance(password, str):
        return False
    if stored.startswith("scrypt"):
        parts = stored.split("$")
        if len(parts) != 6 or not stored.startswith(_HASH_PREFIX):
            return False
        if len(parts[4]) != 32 or len(parts[5]) != 128:
            return False
        try:
            salt, expected = bytes.fromhex(parts[4]), bytes.fromhex(parts[5])
            if len(salt) != 16 or len(expected) != 64:
                return False
            actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=64)
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    if stored.startswith(("$", "argon2", "pbkdf2", "bcrypt", "sha256$", "sha512$")):
        return False
    return hmac.compare_digest(password.encode("utf-8"), stored.encode("utf-8"))


def session_account_binding(provider: str, account) -> str:
    if provider == "local":
        identity = [provider, account.idx, account.userId, account.userPwd]
    elif provider == "kakao":
        identity = [provider, account.id, account.provider, account.provider_user_id]
    else:
        raise ValueError("Invalid session provider")
    message = json.dumps(["session-account-v1", *identity], ensure_ascii=True).encode("utf-8")
    return hmac.new(get_signing_key().encode("utf-8"), message, hashlib.sha256).hexdigest()


def create_session_token(provider: str, account_id: int, binding: str) -> str:
    if provider not in {"local", "kakao"} or type(account_id) is not int or not 0 < account_id <= 2**63 - 1:
        raise ValueError("Invalid session subject")
    if not isinstance(binding, str) or len(binding) != 64 or any(c not in "0123456789abcdef" for c in binding):
        raise ValueError("Invalid session binding")
    payload = {"sub": f"{provider}:{account_id}", "binding": binding,
               "exp": datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)}
    return jwt.encode(payload, get_signing_key(), algorithm=settings.ALGORITHM)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie("token", token, max_age=SESSION_SECONDS, path="/", httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax")
