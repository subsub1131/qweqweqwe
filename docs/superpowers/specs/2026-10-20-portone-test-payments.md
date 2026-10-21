# PortOne V2 테스트 PG 결제

사용자가 PortOne V2 웹훅 문서를 지정하고 테스트 PG 결제 연동을 선택했다. 기존 일반/카카오 인증, 프런트8080→백엔드8000 직접 Axios 통신을 유지한다. 기존 DB 테이블은 바꾸지 않는다. 실제 청구·운영 활성화는 이번 검증에서 수행하지 않는다.

## 저장 및 검증

서버가 상품 가격과 계정 확인값으로 결제 UUID와 주문 스냅샷을 생성한다. 주문은 `data/portone-orders.json`에 원자적으로 저장하고 재시작 시 복원한다. 이 파일은 Git·정적 서비스에서 제외한다. 단일 백엔드 프로세스/worker 전용 테스트 저장소이며 운영 DB의 대체품은 아니다. 기존 상품 목록은 계속 메모리지만 유료 구매 항목은 주문 스냅샷으로 복원한다.

브라우저 결제 결과와 웹훅 모두 같은 결제 조회/상태 동기화 함수를 호출한다. 수강권은 PortOne 조회 결과의 PAID, 주문 ID, store ID, 설정 채널 키, channel.type=TEST, currency=KRW, total/paid 금액, 취소금액0 검증 후에만 표시한다. 금액·상태·계정은 클라이언트 입력을 신뢰하지 않는다. 동일 주문/중복 웹훅 처리 멱등성, 역순 이벤트에서 결제취소가 다시 유효해지지 않도록 보호한다. 취소·부분취소는 해당 주문의 수강권을 제거하며 취소를 실행하는 API는 이번 범위에 없다.

공식 Python SDK `portone-server-sdk==0.21.0`을 사용한다. SDK 웹훅 verify는 원문 UTF-8 body와 헤더를 사용한다. 검증실패400, 설정누락503, 알려지지 않은 유효 이벤트/주문은200무시, 일시적인 조회실패503재시도. 알림 body를 결제 증명으로 쓰지 않고 PortOne API를 다시 조회한다. 로그에 body·signature·secret·주문ID/인가코드 등 원문 민감정보는 남기지 않는다.

## 고정 API 계약

- `GET /api/payments/config` → `{enabled:boolean,mode:"portone-test"}`. enabled는 서버 설정 준비 여부만 뜻한다.
- `POST /api/payments/orders` `{course_id:int}` → `{payment_id:string,status:"PENDING",checkout:{storeId,channelKey,paymentId,orderName,totalAmount,currency:"CURRENCY_KRW",payMethod:"CARD",redirectUrl},course:Course}`. 로그인·Origin 필요. 가격은 서버가 결정.0원은422, 이미 유효한 구매409. 같은 회원/상품의 미완료 주문은 재사용한다.
- `POST /api/payments/confirm` `{payment_id:string}` → `{payment_id,status}`. 로그인·Origin·소유자 검증, 다른 회원 주문404. SDK 성공 표시만으로 완료처리하지 않는다.
- `POST /api/payments/webhook` →200. 서명만으로 외부 호출 인증, 쿠키·Origin 미요구. 호출 본문 제한64KiB.
- `GET /api/my/courses` 기존 `{items:Course[]}` 유지. PORTONE_ENABLED=true일 때 검증된 PAID 주문만 포함한다. 기존 `/api/demo/purchases`는 PORTONE_ENABLED=true이면403으로 차단해 무료 우회 방지.

설정: PORTONE_ENABLED=false 기본값, PORTONE_STORE_ID, PORTONE_CHANNEL_KEY, PORTONE_API_SECRET, PORTONE_WEBHOOK_SECRET, PORTONE_ORDER_FILE=data/portone-orders.json. WEBHOOK_SECRET 포함 모두 준비되어야 enabled=true. 공개키 store/channel은 checkout에만 반환하고 secret은 서버에만 둔다.

## 프런트

기존 상세의 구매 버튼을 ‘PortOne 테스트 결제’로 바꾼다. config미설정 때는 설정필요 안내를 하고 SDK를 호출하지 않는다. 공식 https://cdn.portone.io/v2/browser-sdk.js를 사용하며 CDN은 이 SDK에 한해 필요하다. 주문 checkout을 그대로 requestPayment에 전달하고 성공/팝업닫기/오류/undefined/SDK로딩실패를 처리한다. 성공시 confirm 결과가 PAID일 때만 완료문구. 모바일 redirectUrl은 FRONTEND_URL/courses.html?payment_return=1. paymentId/code/message/pgCode/pgMessage를 읽은 뒤 URL에서 제거하고 오류원문은 화면/콘솔에 반사하지 않는다. 로그인 만료 후에도 주문조회 재시도 안내를 제공한다. 필요한 경우 pending payment ID만 sessionStorage에 보관(쿠키/토큰/키는 저장하지 않음).

## 작업·검증

프런트/백엔드는 기존 별도 worktree를 재사용한다. 백엔드가 결제 서비스·영속 주문·라우터·공식SDK 서명 회귀 테스트를 맡고, 프런트가 결제창·리다이렉트·결과 표시를 맡는다. 실제 키·공개 HTTPS 웹훅 주소가 없으므로 모의 PortOne API와 SDK로 검증하고 실제 PG 결제 성공이라고 보고하지 않는다.

참고: https://developers.portone.io/opi/ko/integration/webhook/readme-v2?v=v2 , https://developers.portone.io/opi/ko/integration/start/v2/checkout?v=v2 , https://portone-io.github.io/server-sdk/py/
