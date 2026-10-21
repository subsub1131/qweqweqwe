from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from api.deps import current_account, require_same_origin
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/providers")
def providers(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"kakao": {"enabled": settings.kakao_enabled()}}


class SessionProfile(BaseModel):
    userId: str
    userNm: str
    email: str | None
    provider: str


@router.get("/me", response_model=SessionProfile)
def me(response: Response, identity=Depends(current_account)):
    response.headers["Cache-Control"] = "no-store"
    provider, account = identity
    if provider == "local":
        return {"userId": account.userId, "userNm": account.userNm, "email": account.email, "provider": provider}
    return {"userId": account.provider_user_id, "userNm": account.display_name, "email": account.email, "provider": provider}


@router.post("/logout", status_code=204, dependencies=[Depends(require_same_origin)])
def logout():
    response = Response(status_code=204)
    response.delete_cookie("token", path="/", httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")
    return response
