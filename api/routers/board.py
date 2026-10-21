from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from app.db.database import SessionLocal
from app.schemas.board import BoardListReq, BoardReq, BoardSearchReq
from app.models.board import Board
from sqlalchemy.orm import Session
from app.db.database import get_db

router = APIRouter(prefix="/board", tags=["board"])

# 목록 조회
@router.post("/boardList")
def boardList(data: BoardListReq, db: Session = Depends(get_db)):
    title = data.title.strip()
    query = select(Board)
    if title:
        query = query.where(Board.title == title)
    boards = db.scalars(query).all()

    if title and not boards:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="등록 된 게시물이 없습니다.")

    return boards

# 목록 조건 조회
@router.post("/boardDt")
def boardDt(data: BoardSearchReq, db: Session = Depends(get_db)):
    boaardDt = db.scalar(select(Board).where(Board.title == data.title))

    if boaardDt is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="없는 게시물")

    return boaardDt

# 등록
@router.post("/insertBoard")
def insertBoard(data: BoardReq):
    db = SessionLocal()

    datas = Board(
        title   = data.title,
        boardCd = data.boardCd
    )

    db.add(datas)
    db.commit()
    db.refresh(datas)

    return datas
