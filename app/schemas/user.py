# 클라이언트와 데이터 통신을 위한 양식 (HTTP 요청 및 응답에 포함 된 데이터)
from pydantic import BaseModel

# 회원가입
class SignData(BaseModel):
    userNm  : str
    userId  : str
    userPwd : str
    email   : str

# 로그인
class LoginReq(BaseModel):
    userId  : str
    userPwd : str

# 로그인 응답
class LoginRes(BaseModel):
    email   : str