# qwer 벚꽃 로그인 화면

## 프론트 소스 관리

프론트 소스는 프로젝트 루트의 `web/` 폴더에서 관리합니다.

```text
web/
├── index.html          # 로그인 화면
├── courses.html        # 강의 화면
├── components.html     # 컴포넌트 미리보기
├── app.js              # 로그인 화면 동작
├── config.js           # 공개 API 주소 설정
├── styles.css          # 공통 스타일
├── cherry-blossom.svg  # 로그인 화면 이미지
├── api/                # API 요청 모듈
├── assets/             # 화면별 스타일, 스크립트, 외부 라이브러리
├── components/         # 재사용 UI 컴포넌트
├── router/             # 화면 라우팅
├── stores/             # 화면 상태 관리
├── views/              # 화면 렌더링
├── tests/              # 프론트 브라우저 테스트
├── package.json        # 프론트 의존성 및 테스트 명령
└── package-lock.json   # 의존성 버전 고정
```

화면 수정과 새 프론트 파일 추가는 `web/` 안에서 진행합니다. `config.js`를 포함한 프론트 파일은 브라우저에 공개되므로 비밀번호나 서버 비밀키를 넣지 않습니다. 백엔드 코드는 루트의 `app/`, `api/`에서 관리하고, 로컬 정적 서버 실행 도구는 루트의 `dev_frontend.py`를 사용합니다.

GitHub Actions의 프론트 배포 워크플로는 `web/**` 변경이 `main`에 반영되면 실행되도록 구성되어 있습니다. 서버 접속 및 실행 명령 설정은 [배포 가이드](../docs/GITHUB-ACTIONS-DEPLOY.md)를 참고합니다.

## 프런트와 백엔드 별도 실행

프로젝트 루트(현재 `C:\JANG\python\qweqweqwe`)에서 터미널 두 개로 실행합니다.

```powershell
# 백엔드: 인증과 API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# 프런트: web/ 정적 파일만 제공. API 프록시 없음.
.\.venv\Scripts\python.exe dev_frontend.py
```

브라우저는 **http://127.0.0.1:8080/** 로 접속합니다. `web/config.js`는 공개 API 주소 `http://127.0.0.1:8000/api`만 지정합니다. 브라우저가 이 주소에 직접 요청하며 프런트 서버는 API를 중계하지 않습니다. 정적 파일은 HTML/CSS/JS/SVG이며 Node 빌드나 CDN이 필요 없습니다.

기존 `.env`는 덮어쓰지 않습니다. DB URL과 시크릿은 서버에만 보관하고 아래 공개 주소 설정을 맞춥니다.

```dotenv
FRONTEND_URL=http://127.0.0.1:8080
COOKIE_SECURE=false
KAKAO_REDIRECT_URI=http://127.0.0.1:8000/api/auth/kakao/callback
```

`SECRET_KEY`는 명시적인 무작위 값(최소 32 UTF-8 바이트)이 필요합니다. 카카오 REST API 키·Client Secret은 `.env`에만 저장합니다. 카카오 키가 없으면 일반 로그인은 사용 가능하며 카카오 버튼은 준비 중으로 표시됩니다. 설치가 필요하면 기존 가상환경에서 `python -m pip install -r requirements.txt`를 실행합니다. 앱 시작 시 지정한 DB에 테이블을 생성하므로 DB URL을 확인합니다. `spring-demo/`는 이 로그인의 인증 서버가 아닙니다.

## 통신과 인증

프런트는 입력 검증·화면 상태·API 요청과 결과 표시를 담당합니다. 백엔드는 비밀번호 검증·해시 저장·카카오 인증·회원 처리·JWT 발급/검증을 수행합니다. 쿠키는 HttpOnly로 유지하며 `credentials: include`로 전송합니다. CORS와 Origin 검증은 `.env`에 지정한 프런트 origin만 허용합니다.

현재 개발 접속 주소와 인증 복귀 주소는 **8080 프런트**입니다. 8000 백엔드 루트로 접속하면 설정된 프런트로 이동합니다. 서버 분리 전에 열어 둔 8000 화면은 새로고침해야 합니다. 기존 Nginx 예시는 과거 선택 구성으로 현재 직접 통신 방식에는 적용하지 않습니다.

## 디버깅

**http://127.0.0.1:8080/?debug=1** 로 열고 F12 → Console에서 `[qwer:http]`를 확인합니다. Network의 API 대상은 8000이어야 합니다. 응답 헤더 `X-Request-ID`와 `logs/http.jsonl`의 `request_id`로 같은 요청을 찾습니다. `?debug=0`으로 끕니다.

```powershell
Get-Content .\logs\http.jsonl -Tail 20 -Wait
```

로그는 상태·시간·경로·요청 ID 등 메타데이터만 포함하며 비밀번호·쿠키·토큰·인가 코드·요청/응답 본문은 포함하지 않습니다. 자세한 제한과 확인 방법은 [통신·로그 안내](../docs/COMMUNICATION-LOGGING.md)를 참고합니다.

## 카카오 로그인

[카카오 설정 안내](../docs/KAKAO-LOGIN-SETUP.md)에 따라 콘솔에 `http://127.0.0.1:8000/api/auth/kakao/callback`을 등록합니다. 인가 요청은 백엔드로 직접 이동하며 `prompt=login`으로 다시 인증합니다. 성공하면 백엔드가 8080 프런트로 이동시킵니다. 서비스 로그아웃은 쿠키를 만료시킵니다.

운영 환경에서는 별도 HTTPS 프런트·백엔드 주소에 맞춰 config.js의 API 주소, FRONTEND_URL, 콜백, Secure 쿠키를 함께 설정합니다. 서로 다른 사이트의 도메인을 사용하는 운영 배포는 쿠키 SameSite와 브라우저의 서드파티 쿠키 정책을 별도로 검토해야 합니다. 현재 검증은 같은 호스트의 다른 포트를 사용하는 로컬 환경입니다.

## 검증

`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`는 임시 SQLite와 모의 카카오 HTTP로 인증·로그·CORS를 검증합니다. 별도 프런트·백엔드 임시 서버와 실제 Chrome으로 직접 API 통신·일반 가입/로그인/로그아웃·쿠키·상태 복원·로그를 검증했습니다. 실제 카카오 로그인은 이전 단일 서버 구성에서 성공을 확인했으며, 이번 분리 구성에서 사용자 재인증은 별도 확인이 필요합니다.

## 온라인 강의 DEMO

같은 정적 서버에서 [courses.html](http://127.0.0.1:8080/courses.html)을 열면 샘플 강의, 상세, 로그인 후 테스트 구매와 내 강의, 강사 체험 등록을 확인할 수 있습니다. PortOne 테스트 채널이 설정되면 테스트 결제창을 이용하며 실제 청구는 하지 않습니다. 영상 재생·강사 권한 구분은 없습니다. 데모 상품은 서버 재시작 시 초기화되며, 결제 주문은 별도로 저장됩니다. 로그인 화면의 강의 링크로도 이동할 수 있습니다.

강의 페이지는 `api/`, `assets/`, `components/`, `router/`, `stores/`, `views/`의 네이티브 모듈과 로컬 Axios를 사용합니다. `npm ci --prefix web`로 의존성을 복원할 수 있습니다. 런타임은 `assets/vendor/axios.min.js`를 사용하므로 Node 빌드는 필요 없습니다. 테스트 결제는 설정 준비 후 공식 PortOne SDK(`https://cdn.portone.io/v2/browser-sdk.js`)를 지연 로드합니다. 설정이 없으면 결제 설정 안내만 표시합니다. Axios 업그레이드 시 설치된 `node_modules/axios/dist/axios.min.js`, 대응 `.map`, `LICENSE`를 vendor 폴더에 함께 복사합니다.

모의 API 브라우저 검증: `node web/tests/course-demo.cjs`, `node web/tests/payments.cjs` (또는 `npm test --prefix web`). 기본값은 이 장치에 설치된 Playwright/Chrome이며 다른 환경에서는 `PLAYWRIGHT_MODULE`과 `CHROME_PATH` 환경 변수로 경로를 지정합니다. 임시 정적 서버는 검증 후 자동 종료합니다. 이 검증은 실제 인증·Origin 검증을 대체하지 않습니다.

결제창 반환값으로 수강권을 부여하지 않고 서버 확인 결과가 `PAID`일 때만 완료를 표시합니다. 모바일 반환 필드는 URL에서 즉시 지우며 원문 오류는 표시하거나 로그에 남기지 않습니다. 확인 중·네트워크 오류·로그인 만료 때 결제 상태 재확인이 가능하고, 세션 저장소에는 재확인할 결제 ID만 보관합니다. 로컬 프런트 서버도 결제 반환 쿼리를 액세스 로그에 기록하지 않도록 프로젝트의 쿼리 제외 개발 서버를 사용하세요.
