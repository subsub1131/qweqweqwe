import {paymentApi, loadPaymentSdk} from '../api/payments.js';

const pendingKey = 'qwer.pendingPayment';
const validId = id => typeof id === 'string' && /^[a-zA-Z0-9_-]{1,100}$/.test(id);
function rememberedId() {
  try { const id = sessionStorage.getItem(pendingKey); return validId(id) ? id : null; } catch { return null; }
}

export function startPayments({onPaid, onMessage}) {
  const panel = document.getElementById('payment-status');
  const message = document.getElementById('payment-message');
  const retryButtons = ['payment-retry', 'detail-payment-retry'].map(id => document.getElementById(id));
  const purchaseButton = document.getElementById('purchase-button');
  let pendingId = rememberedId();
  let busy = false;

  function remember(id) {
    pendingId = id;
    try { if (id) sessionStorage.setItem(pendingKey, id); else sessionStorage.removeItem(pendingKey); } catch { /* Retry still works in this page when storage is blocked. */ }
  }
  function show(text, canRetry = Boolean(pendingId)) {
    panel.hidden = false;
    message.textContent = text;
    for (const button of retryButtons) button.hidden = !canRetry;
    onMessage(text);
  }
  function setBusy(value) {
    busy = value;
    for (const button of retryButtons) button.disabled = value;
    purchaseButton.disabled = value;
  }
  function requestError(error, operation) {
    const status = error.response?.status;
    if (status === 401) return '로그인이 필요해요. 로그인한 뒤 이 화면으로 돌아와 결제 상태를 다시 확인해 주세요.';
    if (status === 403) return '요청을 확인할 수 없어요. 로그인 상태를 확인하고 다시 시도해 주세요.';
    if (status === 404) return '이 계정에서 주문을 확인할 수 없어요. 결제한 계정으로 로그인해 주세요.';
    if (status === 409 && operation === 'order') return '이미 구매한 강의예요. 내 강의에서 확인해 주세요.';
    if (status === 409) return '결제 검증에 실패했어요. 결제가 완료된 것으로 확인되지 않았어요. 결제 상태를 다시 확인해 주세요.';
    if (status === 422) return '이 상품은 테스트 결제를 진행할 수 없어요. 가격과 상품 정보를 확인해 주세요.';
    if (status === 503) return '결제 설정 또는 결제 조회가 준비되지 않았어요. 잠시 후 다시 확인해 주세요.';
    return '연결을 확인한 뒤 결제 상태를 다시 확인해 주세요. 아직 결제 완료로 확인되지 않았어요.';
  }
  async function confirm() {
    show('결제 상태를 확인 중이에요…');
    try {
      const result = await paymentApi.confirm(pendingId);
      if (result.status === 'PAID') {
        remember(null);
        show('테스트 결제 확인 완료! 내 강의에서 확인할 수 있어요.', false);
        await onPaid();
      } else if (result.status === 'CANCELLED' || result.status === 'PARTIAL_CANCELLED') {
        remember(null);
        show('취소된 결제예요. 이 주문으로는 수강할 수 없어요.', false);
      } else if (result.status === 'FAILED') {
        remember(null);
        show('결제에 실패했어요. 강의 상세에서 다시 시작해 주세요.', false);
      } else {
        show('결제 상태를 확인 중이에요. 아직 완료되지 않았어요. 잠시 후 다시 확인해 주세요.');
      }
    } catch (error) { show(requestError(error, 'confirm')); }
  }
  async function retryConfirmation() {
    if (busy || !pendingId) return;
    setBusy(true);
    try { await confirm(); } finally { setBusy(false); }
  }
  for (const button of retryButtons) button.addEventListener('click', retryConfirmation);

  async function purchase(courseId) {
    if (busy) return;
    setBusy(true);
    try {
      show('테스트 결제 설정을 확인 중이에요…', false);
      const config = await paymentApi.config();
      if (config.enabled !== true || config.mode !== 'portone-test') {
        show('PortOne 테스트 채널 설정이 필요해요. 설정이 준비되면 테스트 결제를 이용할 수 있어요.', false);
        return;
      }
      const order = await paymentApi.order(courseId);
      if (!validId(order.payment_id)) { show('주문을 확인하지 못했어요. 잠시 후 다시 시도해 주세요.', false); return; }
      remember(order.payment_id);
      let sdk;
      try { sdk = await loadPaymentSdk(); }
      catch { show('결제창을 불러오지 못했어요. 연결을 확인하고 강의 상세에서 다시 시작해 주세요.'); return; }
      let result;
      show('PortOne 테스트 결제창에서 진행해 주세요.');
      // A modal dialog occupies the browser top layer above PG iframe overlays.
      const detailDialog = document.getElementById('course-dialog');
      const restoreDetail = detailDialog?.open;
      if (restoreDetail) detailDialog.close();
      try { result = await sdk.requestPayment(order.checkout); }
      catch { show('결제가 취소되었거나 결제창을 닫았어요. 결제 상태를 다시 확인할 수 있어요.'); return; }
      finally { if (restoreDetail && detailDialog.isConnected && !detailDialog.open) detailDialog.showModal(); }
      if (result === undefined) {
        show('결제 화면으로 이동 중일 수 있어요. 돌아오면 결제 상태를 확인해 주세요.');
        return;
      }
      if (!result || Object.hasOwn(result, 'code')) {
        show('결제가 취소되었거나 결제창을 닫았어요. 결제 상태를 다시 확인할 수 있어요.');
        return;
      }
      // Provider response fields never prove payment. Verify our server-created order.
      await confirm();
    } catch (error) { show(requestError(error, 'order')); }
    finally { setBusy(false); }
  }

  const returned = window.QWER_PAYMENT_RETURN;
  if (returned?.returned) {
    if (returned.paymentId) remember(returned.paymentId);
    if (returned.hasError) show('결제가 취소되었거나 진행되지 않았어요. 결제 상태를 다시 확인할 수 있어요.');
    else if (pendingId) retryConfirmation();
    else show('돌아온 결제의 주문을 확인할 수 없어요. 결제한 계정으로 로그인하고 다시 시도해 주세요.', false);
  } else if (pendingId) {
    show('이전에 진행한 결제가 있어요. 결제 상태를 다시 확인해 주세요.');
  }
  return {purchase};
}
