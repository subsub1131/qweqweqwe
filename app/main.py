#  보안상 중요한 값이나 기능을 모아둔 파일
# ex) 토큰 생성, pwd 암호화 등
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from urllib.parse import urlsplit
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from api.routers.users import router
from api.routers.board import router as board_router
from api.routers.auth import router as auth_router
from api.routers.kakao import router as kakao_router
from api.routers.courses import router as courses_router
from api.routers.payments import router as payments_router
from app.db.database import Base, engine
from app.models.user import User
from app.models.board import Board
from app.models.social_account import SocialAccount
from app.core.config import settings, valid_http_url
from app.core.request_logging import RequestLogMiddleware

app = FastAPI(title="qwerAPI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_URL.rstrip('/')],
                   allow_credentials=True, allow_methods=['GET', 'POST'],
                   allow_headers=['Content-Type', 'X-Request-ID'], expose_headers=['X-Request-ID'])
app.add_middleware(RequestLogMiddleware)


@app.exception_handler(RequestValidationError)
async def safe_auth_validation(request: Request, exc: RequestValidationError):
    if request.url.path.rstrip("/") in {"/user/login", "/user/signUp", "/api/user/login", "/api/user/signUp"}:
        return JSONResponse(status_code=422, content={"detail": "Invalid authentication input."},
                            headers={"Cache-Control": "no-store"})
    return await request_validation_exception_handler(request, exc)

for api_router in (router, board_router, auth_router, kakao_router):
    app.include_router(api_router)
    app.include_router(api_router, prefix="/api", include_in_schema=False)
app.include_router(courses_router)
app.include_router(payments_router)
Base.metadata.create_all(bind=engine)

@app.get('/', include_in_schema=False)
async def frontend_entry(request: Request):
    if not valid_http_url(settings.FRONTEND_URL):
        return JSONResponse(status_code=503, content={'detail': 'Frontend URL is not configured.'})
    frontend = urlsplit(settings.FRONTEND_URL)
    frontend_origin = f'{frontend.scheme}://{frontend.netloc}'
    if str(request.base_url).rstrip('/') != frontend_origin:
        target = settings.FRONTEND_URL.rstrip('/') + '/'
        debug = request.query_params.get('debug')
        if debug in {'0', '1'}:
            target += '?debug=' + debug
        return RedirectResponse(target, status_code=307)
    return FileResponse(Path(__file__).resolve().parents[1] / 'web' / 'index.html')

# Keep API routes before the static catch-all. Only web/ is public.
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "web", html=True), name="web")


