# 신규 로그인 및 카카오 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 웹 화면을 모두 교체하고 일반 로그인 및 설정 후 사용 가능한 카카오 로그인을 제공한다.

**Architecture:** 기존 FastAPI와 Nginx의 `/api/` 프록시 구조를 유지한다. 서버에서 비밀번호·OAuth·JWT 쿠키를 처리하고 새 정적 프런트는 로그인·회원가입·로그인 완료 상태만 표시한다. 소셜 계정은 일반 계정과 별도 테이블에서 관리한다.

**Tech Stack:** Python, FastAPI, SQLAlchemy, PyJWT, httpx, 표준 라이브러리 scrypt/unittest, HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-20-login-kakao-design.md` — 사용자 승인 완료.

## Global Constraints

- 기존 `web/index.html`, `web/styles.css`, `web/app.js`, `web/README.md`의 내용을 폐기하고 같은 위치에 새 로그인 전용 프런트엔드를 구성한다.
- 삭제 범위는 기존 웹 화면 전체이다. 실제 사용자 데이터 삭제, 외부 배포, 카카오 앱 생성은 이번 작업에 포함하지 않는다.
- 기존 `.env`는 덮어쓰거나 비밀값을 보고서에 기록하지 않는다.
- 새 프런트엔드는 Node 빌드나 외부 CDN을 요구하지 않는다.
- 실제 키가 없는 상태에서는 모의 통신 검증까지 수행하며 실제 카카오 로그인 성공으로 보고하지 않는다.
- 현재 루트는 Git 저장소가 아니므로 문서 커밋이나 worktree 생성은 수행하지 않는다.

## Review Focus

1. 기존 평문 비밀번호와 손상된 해시: 성공한 평문 계정만 전환하고 잘못된 값은 인증을 거부한다.
2. 카카오 사용자 정보에 이메일·닉네임이 없음: 로그인에 성공하고 기본 표시 이름을 사용한다.
3. 동일 카카오 회원의 동시 가입: 고유 제약과 충돌 후 재조회로 같은 회원을 반환한다.
4. 위조·만료 OAuth state와 잘못된 JWT: 외부 토큰 요청 또는 회원 정보 반환 전에 거부한다.
5. 프록시 경로 및 모바일 긴 오류: `/api/` 접두사는 한 번만 사용하며 작은 화면에서 입력과 오류가 잘리지 않는다.

## 공통 인터페이스

- `POST /user/signUp`: 기존 `userNm`, `userId`, `userPwd`, `email` 입력. 응답 `{userId, userNm, email}`. 성공 201, 중복 409.
- `POST /user/login`: `{userId, userPwd}`. 성공 200과 사용자 정보, 잘못된 자격증명 401. 성공 시 `token` HttpOnly 쿠키.
- `GET /auth/me`: `{userId, userNm, email, provider}`. `provider`는 `local` 또는 `kakao`. 미인증 401, `Cache-Control: no-store`.
- `POST /auth/logout`: 성공 204와 `token` 쿠키 만료. state 변경 POST는 Origin이 있으면 설정된 프런트 origin과 일치해야 하며 불일치는 403. Origin 없는 직접 API 호출은 허용한다.
- `GET /auth/providers`: `{kakao: {enabled: boolean}}`. 키·시크릿·전체 설정을 노출하지 않는다.
- `GET /auth/kakao/login`: 활성화 시 카카오 인가 URL로 302. 키 미설정 시 503.
- `GET /auth/kakao/callback`: 성공·실패 모두 설정된 프런트 루트로 303. 오류는 `?auth_error=<허용된 코드>`만 전달한다.
- JWT: `sub=local:<User.idx>` 또는 `sub=kakao:<SocialAccount.id>`, `exp` 30분, 허용 알고리즘은 `settings.ALGORITHM`으로 고정. 세션 쿠키도 1800초.
- OAuth state: `secrets.token_urlsafe(32)`로 생성, 쿠키는 `kakao_oauth_state`, HttpOnly, SameSite=Lax, 600초. 서명된 state 쿠키의 만료·nonce를 검증하며 콜백 응답에서 삭제한다. 정상적으로 토큰 교환된 인가 코드는 재사용할 수 없다.
- 오류 코드: `kakao_cancelled`, `invalid_state`, `kakao_unavailable`, `kakao_failed`. 카카오 반환 설명이나 토큰은 노출하지 않는다.
- 설정: `FRONTEND_URL=http://localhost:8080`, `COOKIE_SECURE=false`, 비어 있는 카카오 키·시크릿·Redirect URI 기본값. `SECRET_KEY`는 명시적 값 필수이며 기존의 알려진 기본 키는 거부한다.

### Task 1: 일반 인증과 공통 세션

**Files:**
- Modify: `app/core/config.py`, `app/core/security.py`, `api/routers/users.py`, `api/routers/auth.py`, `api/deps.py`, `app/main.py`, `requirements.txt`
- Create: `app/models/social_account.py`, `.env.example`, `tests/__init__.py`, `tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `get_db`, 기존 회원가입·로그인 입력 스키마.
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, stored: str) -> bool`, `create_session_token(provider: str, account_id: int) -> str`, `set_session_cookie(response: Response, token: str) -> None`, `require_same_origin(request: Request) -> None`.
- Produces: `SocialAccount` 모델: `id` 정수 PK, `provider` 문자열, `provider_user_id` 문자열, `display_name` 문자열, `email` nullable 문자열, `(provider, provider_user_id)` 고유 제약.
- Produces: 일반 인증, me, logout API. `app/main.py`는 새 모델을 테이블 생성 전에 import하고 auth router를 등록한다.

- [ ] **Step 1: 실패 테스트 작성.** `tests/test_auth.py`에 임시 DB와 `get_db` override를 사용하는 TestClient를 만든다. 테스트 시작 전에 환경변수로 테스트 전용 DB URL·시크릿을 지정하고 실제 `.env` 로딩을 차단한다. 해시·손상 해시·정상/실패 로그인·평문 전환·응답 필터·중복 가입·쿠키·만료 JWT·삭제 회원·Origin 불일치·로그아웃을 검증한다. 다음 핵심 검증을 포함한다.

```python
def test_wrong_password_is_rejected(self):
    self.seed_local_user('tester', 'correct-password')
    response = self.client.post('/user/login', json={
        'userId': 'tester', 'userPwd': 'incorrect-password'})
    self.assertEqual(response.status_code, 401)
    self.assertNotIn('token', response.cookies)
```

- [ ] **Step 2: 실패 확인.** `.\.venv\Scripts\python.exe -m unittest tests.test_auth -v`를 실행하여 신규 요구에 대한 실패를 확인한다. 패키지가 없으면 승인된 범위의 런타임 의존성을 기존 환경에 설치하고 재실행한다.
- [ ] **Step 3: 구현.** 표준 `hashlib.scrypt`를 `n=16384, r=8, p=1, dklen=64`, 랜덤 salt 16바이트로 사용하고 형식에 알고리즘·파라미터·salt·해시를 기록한다. 해시 파라미터는 구현의 허용 값만 처리한다. 검증에 `hmac.compare_digest`를 사용한다. 올바른 기존 평문은 로그인 성공 시 해시로 갱신한다. 세션 검증은 서명·exp·provider·숫자 ID·DB 회원 존재를 확인한다. 명시적인 안전한 JWT 키를 요구하고 설정 누락은 안내 가능한 오류로 처리한다. 응답 DTO에서 비밀번호를 제외하고 DB 세션을 의존성으로 통일한다. 필요한 SQLAlchemy·PyJWT 의존성을 명시한다.
- [ ] **Step 4: 통과 확인.** 같은 unittest 명령을 실행하고 Task 1 테스트 전체가 통과하는지 확인한다. 실제 DB와 `.env`가 변경되지 않았는지 작업 파일 목록을 확인한다.

### Task 2: 카카오 OAuth 서버 흐름

**Files:**
- Create: `app/services/__init__.py`, `app/services/kakao.py`, `api/routers/kakao.py`, `tests/test_kakao.py`
- Modify: `app/core/config.py`, `api/routers/auth.py`, `app/main.py`, `.env.example`

**Interfaces:**
- Consumes: Task 1의 `SocialAccount`, 공통 세션 토큰·쿠키 함수, 설정.
- Produces: `fetch_kakao_profile(code: str) -> dict` 비동기 함수. `httpx.AsyncClient`의 10초 타임아웃으로 토큰 교환과 사용자 정보 조회를 처리한다.
- Produces: providers, kakao/login, kakao/callback API와 테스트 가능한 소셜 계정 조회·생성 처리.
- 카카오 endpoint는 `https://kauth.kakao.com/oauth/authorize`, `https://kauth.kakao.com/oauth/token`, `https://kapi.kakao.com/v2/user/me`로 고정한다.

- [ ] **Step 1: 실패 테스트 작성.** `tests/test_kakao.py`에서 Task 1의 임시 DB fixture를 사용하고 httpx 요청은 mock transport 또는 함수 patch로 대체한다. 키 누락·인가 URL·state 쿠키·누락/변조/만료 state·취소·토큰/프로필 실패·기본 닉네임·이메일 미제공·반복 회원·고유 제약 충돌 후 재조회를 검증한다. 실패 시 외부 토큰 요청이 발생하지 않는지 확인한다.

```python
def test_missing_state_does_not_exchange_code(self):
    with patch('api.routers.kakao.fetch_kakao_profile') as exchange:
        response = self.client.get('/auth/kakao/callback?code=test-code',
                                   follow_redirects=False)
    self.assertEqual(response.status_code, 303)
    self.assertIn('auth_error=invalid_state', response.headers['location'])
    exchange.assert_not_called()
```

- [ ] **Step 2: 실패 확인.** `.\.venv\Scripts\python.exe -m unittest tests.test_kakao -v`를 실행하여 새 API 또는 요구된 보호 동작이 없어서 실패하는지 확인한다.
- [ ] **Step 3: 구현.** 공통 인터페이스의 state·오류·경로 계약대로 작성한다. 토큰 교환은 form encoding, 사용자 조회는 Bearer 인증을 사용한다. Client Secret은 설정 시에만 전송한다. 카카오 회원번호를 검증하고 이메일로 자동 연결하지 않는다. 고유 제약 충돌 시 rollback 후 기존 소셜 회원을 조회한다. 카카오 토큰은 저장하지 않는다. 로그인 시작과 콜백 응답 모두 no-store를 사용한다.
- [ ] **Step 4: 통과 확인.** `.\.venv\Scripts\python.exe -m unittest tests.test_auth tests.test_kakao -v`를 실행하고 실제 카카오 네트워크 호출 없이 통과하는지 확인한다.

### Task 3: 기존 화면 전체 교체 및 연결 안내

**Files:**
- Replace: `web/index.html`, `web/styles.css`, `web/app.js`, `web/README.md`
- Create: `docs/KAKAO-LOGIN-SETUP.md`
- Modify: `deploy/nginx.conf.example` — 신규 화면 배포 설명만 필요한 경우 반영.

**Interfaces:**
- Consumes: Task 1·2의 API. 브라우저는 같은 origin의 `/api/user/...`, `/api/auth/...`를 호출한다.
- Produces: 로그인·회원가입·인증 완료의 새 화면, providers 기반 카카오 버튼 상태, 세션 복원, 로그아웃, 허용된 auth_error의 한국어 메시지 매핑.

- [ ] **Step 1: 새 화면 작성.** 기존 네 파일의 내용을 전부 교체한다. 디자인은 밝은 배경·짙은 글자·녹색 포인트의 소개/카드 2열, 760px 이하 단일 열로 구현한다. 모바일 입력은 16px 이상, 입력·버튼은 44px 이상 높이를 확보한다. 라벨·focus-visible·상태 안내·비밀번호 표시 토글·비밀번호 관리자 자동완성을 포함한다. 게시판 DOM과 동작은 남기지 않는다.
- [ ] **Step 2: API 연결.** 공통 fetch 함수는 `credentials: include`, 15초 타임아웃, 중복 제출 방지, JSON/비JSON 오류 처리를 제공한다. 인증 시 비밀번호를 다시 표시하지 않는다. me의 401은 일반 미로그인 상태로 처리하며 장애와 구분한다. 카카오 버튼은 providers 로딩·미설정 때 비활성화한다. auth_error를 읽은 뒤 URL에서 제거한다. 서버 인증 완료 후 사용자 카드만 표시한다.
- [ ] **Step 3: 문서 작성.** 기존 `.env`를 보존하면서 필요한 설정을 사용자가 추가하는 방법, localhost:8080 프런트와 localhost:8000 API를 연결하는 Nginx 예시, 카카오 외부 콜백 `http://localhost:8080/api/auth/kakao/callback`, 운영 HTTPS와 Secure 쿠키 설정, 최초 실행 명령을 설명한다. 키는 채팅이나 프런트 JS에 넣지 않고 서버 설정에만 둔다. Java 데모가 인증 서버가 아님을 명시한다.
- [ ] **Step 4: 화면 검증.** 임시 테스트 서버/모의 API를 이용해 1440px·390px 화면을 확인한다. 로그인 성공·실패·회원가입·세션 복원·로그아웃·카카오 미설정·오류 콜백·타임아웃·긴 한국어 오류·키보드 조작을 확인한다. 실제 DB를 사용하는 앱 import/서버 시작은 피한다. 브라우저 조작 도구를 사용할 수 없으면 검증하지 못한 항목을 명확히 보고한다.
- [ ] **Step 5: 최종 검증.** `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`를 실행한다. 사용 가능한 JS 구문 검사 도구로 `web/app.js`를 검사하고 기존 게시판 DOM 식별자가 사라졌는지 `rg`로 확인한다. 실패가 있으면 systematic-debugging으로 원인을 좁혀 수정한다. 실제 키 미설정 시 카카오 실로그인을 검증하지 않았음을 결과에 적는다.

## 실행 검토

설계 요구사항은 Task 1(일반 인증·세션), Task 2(카카오), Task 3(화면·문서·시각 검증)에 배정되어 있다. Review Focus의 1·4는 Task 1/2 테스트, 2·3은 Task 2 테스트, 5는 Task 3 검증에 배정했다.

추천 실행 방식은 **직접 구현(Native)** 이다. 세 작업이 공통 인증 API와 쿠키 계약을 순차적으로 공유하므로 현재 세션에서 이어서 구현하면 문맥 전달 비용을 줄일 수 있다. 사용자가 병렬 에이전트 방식을 선택하면 해당 방식의 Superpowers 지침을 적용한다.

현재 상태 (2026-10-20 재개): Task 1~3 구현 및 기존 화면 교체 완료. 최종 리뷰의 후속 수정 4건도 반영했으며, 전체 백엔드 테스트 42개가 통과했다. 실행·리뷰 근거는 `.superpowers/sdd/login-kakao/progress.md`와 `resume-report.md`에 있다. 위 단계별 체크박스는 최초 계획 작성 시점의 기록이다. 실제 카카오 로그인과 기존 서버 배포 검증은 도메인·카카오 앱 설정 확인 후 진행한다.
