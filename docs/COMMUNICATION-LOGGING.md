# 프런트 → 백엔드 직접 통신 및 로그

## 로컬 주소

- 프런트: `http://127.0.0.1:8080/` — HTML/CSS/JS를 제공하는 정적 서버
- 백엔드: `http://127.0.0.1:8000` — FastAPI
- 프런트 API 설정: `web/config.js`의 `apiBaseUrl=http://127.0.0.1:8000/api`
- 서버 허용 프런트: `.env`의 `FRONTEND_URL=http://127.0.0.1:8080`
- 카카오 콜백: `http://127.0.0.1:8000/api/auth/kakao/callback`

브라우저 JavaScript가 절대 주소의 백엔드 API를 직접 호출합니다. `/api`는 FastAPI의 라우트 이름이며, 프런트 서버의 프록시 경로가 아닙니다. 프런트 정적 서버는 API를 중계하지 않습니다. 카카오 로그인 시작도 브라우저에서 백엔드로 직접 이동하고, 인증 완료 후 백엔드가 프런트 8080으로 돌려보냅니다.

쿠키는 `credentials: include`로 브라우저가 자동 전송합니다. 프런트 JavaScript는 HttpOnly 세션 쿠키를 읽지 않습니다. CORS는 설정된 프런트 origin만 허용하며, 백엔드의 Origin 검증도 유지합니다. 프런트와 백엔드에 `localhost`와 `127.0.0.1`을 섞어 사용하지 마세요.

## 브라우저에서 확인

1. `http://127.0.0.1:8080/?debug=1`로 엽니다.
2. F12 → Console에서 `[qwer:http]`로 필터링합니다.
3. Network의 API 요청 주소가 `http://127.0.0.1:8000/api/...`인지 확인합니다.
4. 요청·응답 헤더의 `X-Request-ID`를 서버 로그의 `request_id`와 비교합니다.
5. 카카오 이동 전후 로그를 보려면 개발자 도구의 Preserve log를 켭니다. 이동 요청은 fetch가 아니므로 Network에서 302와 콜백 요청의 ID를 확인합니다. 각 HTTP 요청의 ID는 다르며 전체 OAuth 흐름을 묶는 ID는 아닙니다.

`?debug=0`으로 열면 브라우저 로그가 꺼집니다. 디버그 플래그만 현재 탭 sessionStorage에 보관하며 인증정보를 저장하지 않습니다. 브라우저 로그는 메서드·경로·상태·처리시간·요청 ID·결과만 기록합니다. 네트워크·CORS·타임아웃으로 응답을 못 받으면 status는 0입니다. 서버의 처리되지 않은 500은 CORS 헤더가 누락될 수 있으므로 같은 요청 ID로 서버 로그도 확인합니다.

개발자 도구의 Network 자체에는 인증 응답·헤더가 보일 수 있습니다. 여기서 설명하는 민감정보 제외 정책은 애플리케이션이 생성하는 로그에 적용됩니다. Network 원본 전체를 그대로 공유하지 마세요.

## 백엔드에서 확인

프로젝트 루트의 `logs/http.jsonl`에 JSON 한 줄씩 저장합니다. 시간은 UTC ISO 8601이며, 최대 약 1MB씩 현재 파일과 이전 3개 파일을 순환 보관합니다. 같은 메타데이터가 백엔드 터미널에도 출력됩니다.

```powershell
Get-Content .\logs\http.jsonl -Tail 20 -Wait
# 특정 요청만 찾기
Select-String -Path .\logs\http.jsonl -SimpleMatch '<X-Request-ID 값>'
```

비밀번호·계정 입력·요청/응답 본문·쿠키·Authorization·키·토큰·인가 코드·state·URL 쿼리·IP는 기록하지 않습니다. 카카오 콜백은 허용된 `auth_result` 오류 코드 또는 success만 추가합니다. 모르는 경로는 `[unmatched]`로 기록합니다. Uvicorn 기본 접근 로그에도 쿼리 제거 필터를 적용합니다. 프런트에 로그를 읽는 API를 공개하지 않습니다.

## 역할

프런트는 HTML 입력 검증, 요청 전송, 로딩·오류·결과 표시를 담당합니다. 백엔드는 입력 재검증, 비밀번호·카카오 인증, 회원 조회/생성, JWT 검증과 쿠키를 담당합니다. 직접 API 통신을 위해 시크릿이나 토큰을 프런트에 전달하지 않습니다.
