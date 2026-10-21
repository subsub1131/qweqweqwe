from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_same_origin
from app.core.security import AuthConfigurationError, create_session_token, get_signing_key, hash_password, session_account_binding, set_session_cookie, verify_password
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import LoginReq, SignData

router = APIRouter(prefix="/user", tags=["user"], dependencies=[Depends(require_same_origin)])


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    userId: str
    userNm: str
    email: str


@router.post("/signUp", status_code=201, response_model=UserProfile)
def signup(data: SignData, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.userId == data.userId)) is not None:
        raise HTTPException(status_code=409, detail="This user ID is already registered.")
    user = User(userNm=data.userNm, userId=data.userId, userPwd=hash_password(data.userPwd), email=data.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserProfile)
def login(req: LoginReq, res: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.userId == req.userId))
    if user is None or not verify_password(req.userPwd, user.userPwd):
        raise HTTPException(status_code=401, detail="Invalid user ID or password.")
    try:
        get_signing_key()
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not user.userPwd.startswith("scrypt$"):
        user.userPwd = hash_password(req.userPwd)
        db.commit()
    token = create_session_token("local", user.idx, session_account_binding("local", user))
    set_session_cookie(res, token)
    return user
