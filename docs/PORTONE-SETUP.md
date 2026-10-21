# PortOne V2 테스트 PG 연결

현재 연동 대상은 **테스트 PG 카드 결제**입니다. 운영 결제 전환·실제 청구·환불 실행은 이번 구현/검증 범위에 포함하지 않습니다.

## 서버 설정

기존 `.env`의 아래 항목을 서버에서만 입력합니다. API Secret과 웹훅 Secret은 채팅·브라우저 코드·스크린샷에 넣지 않습니다.

```dotenv
PORTONE_ENABLED=true
PORTONE_STORE_ID=<포트원 상점 ID>
PORTONE_CHANNEL_KEY=<반드시 테스트 채널 키>
PORTONE_API_SECRET=<V2 API Secret>
PORTONE_WEBHOOK_SECRET=<테스트 모드 웹훅 Secret>
PORTONE_ORDER_FILE=data/portone-orders.json
```

키 미설정 시 `PORTONE_ENABLED=false`로 유지합니다. 설정이 준비되지 않으면 프런트는 결제 준비 필요 상태를 보여주며 가짜 결제 성공을 표시하지 않습니다. `enabled=true`도 키 유효성이나 PG 연결 성공을 보장하는 값은 아닙니다.

PortOne 관리자 콘솔에서 V2 **테스트** PG 채널을 준비하고 해당 상점/채널의 설정값을 사용합니다. 결제 조회 응답의 채널이 TEST가 아니거나 설정 채널·상점·금액·통화와 다르면 백엔드는 수강권을 발급하지 않습니다. 운영 채널을 실수로 입력해도 결제창의 실제 청구를 서버가 사전에 막아 주는 것은 아니므로, 반드시 콘솔에서 테스트 채널임을 먼저 확인합니다.

## 웹훅

PortOne 관리자 콘솔의 결제알림(Webhook) 관리에서 결제모듈 V2, 테스트 모드, 최신 2024-04-25 형식, application/json을 선택합니다. 수신 경로는 아래와 같습니다.

```text
https://<공개 HTTPS 백엔드 주소>/api/payments/webhook
```

PortOne 서버에서 이 주소로 요청하므로 `127.0.0.1:8000`은 외부 웹훅 주소로 사용할 수 없습니다. 공개 테스트 서버나 승인한 로컬 터널을 별도로 준비한 뒤 등록합니다. 이 작업에서는 공개 터널·외부 배포·콘솔 변경을 자동으로 수행하지 않습니다. 웹훅 시크릿도 같은 **테스트 모드**에서 발급받습니다.

서버는 원문 body로 공식 SDK의 서명/시간 검증을 수행하고, 알려진 주문의 실제 결제 상태를 PortOne API에서 재조회합니다. 알림에 적힌 PAID 상태나 클라이언트의 성공 결과만으로 결제 완료를 신뢰하지 않습니다. 웹훅 중복은 재발급하지 않으며, 알 수 없는 유효 이벤트는 무시합니다. 잘못된 서명400, 일시적 조회 장애503 응답으로 재시도를 허용합니다.

## 로컬 실행과 로그

프로젝트 루트에서 별도 터미널로 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe dev_frontend.py
```

프런트 `http://127.0.0.1:8080/courses.html`에서 브라우저가 백엔드8000을 직접 호출합니다. 프런트 서버는 API를 프록시하지 않습니다. `dev_frontend.py`는 모바일 결제 복귀 URL의 쿼리를 접근 로그에서 제외합니다. PortOne 브라우저 SDK에 한해 공식 CDN을 사용하며 CDN 로딩 실패는 별도 안내합니다.

개발자 콘솔은 `?debug=1`로 켭니다. 서버의 `logs/http.jsonl`과 X-Request-ID로 요청을 연결합니다. 요청/응답 본문, 결제 서명, Secret, 쿠키·토큰, 모바일 오류 원문은 애플리케이션 로그에 기록하지 않습니다.

## 주문 저장과 제한

기존 회원 DB와 테이블은 변경하지 않습니다. 주문은 별도 JSON 파일에 저장하며 상품 스냅샷과 계정 확인값, 금액, 상태만 보관합니다. 결제수단 상세·카드 정보·API 원문 응답은 저장하지 않습니다. 이 파일은 정적 web/ 밖에 있고 Git에서 제외됩니다.

현재 파일 저장소는 **로컬 테스트/단일 worker**용입니다. 운영 전에는 공유해 주실 주문·결제 DB 스키마와 회원 식별 체계로 교체해야 합니다. 백엔드의 시크릿 변경·회원 비밀번호 변경은 현재 계정 확인값에 영향을 줄 수 있습니다. 여러 인스턴스에서 같은 파일을 공유하는 운영 구성은 지원하지 않습니다.

## 검증 구분

키 없는 상태에서는 모의 PortOne API·모의 브라우저 SDK와 실제 SDK 서명 검증으로 연동 로직을 검증합니다. 실제 PG 결제창에서 사용자 인증 완료, PortOne 외부 웹훅 도착, 콘솔 내 테스트 결제 확인은 별도 테스트 설정 후 수행해야 합니다.

공식 문서: [V2 웹훅](https://developers.portone.io/opi/ko/integration/webhook/readme-v2?v=v2), [인증 결제](https://developers.portone.io/opi/ko/integration/start/v2/checkout?v=v2), [Python SDK](https://portone-io.github.io/server-sdk/py/).
