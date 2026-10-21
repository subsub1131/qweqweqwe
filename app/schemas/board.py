from pydantic import BaseModel

class Board(BaseModel):
    boardId : int
    title   : str
    boardCd : str

class BoardReq(BaseModel):
    title   : str
    boardCd : str

class BoardSearchReq(BaseModel):
    title   : str

class BoardListReq(BaseModel):
    title   : str = ""
