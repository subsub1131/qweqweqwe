# db와 1:1로 매핑되는 파일 (VO)
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class User(Base):
    __tablename__="user"

    idx:Mapped[int] = mapped_column(primary_key=True)

    userNm      : Mapped[str]=mapped_column()
    userId      : Mapped[str]=mapped_column()
    userPwd     : Mapped[str]=mapped_column()
    email       : Mapped[str]=mapped_column()
