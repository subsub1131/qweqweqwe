# DB 서버와 연결 및 설정
# ORM : Object Relation Mapping
# 객체 : 현실 세상의 무언가를 컴퓨터 코드로 옮긴 것
# 개체 : 현실 세상의 무언가를 컴푸터 데이터로 옮긴 것
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)           # 엔진
SessionLocal = sessionmaker(autoflush=False, bind=engine)   # 도구

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 부모 클라쓰
class Base(DeclarativeBase):
    pass
