(() => {
  // Consume provider return fields before any module can initialize diagnostics.
  const url = new URL(location.href);
  const fields = ['payment_return', 'paymentId', 'code', 'message', 'pgCode', 'pgMessage'];
  const returned = fields.some(key => url.searchParams.has(key));
  const rawId = url.searchParams.get('paymentId');
  const paymentId = typeof rawId === 'string' && /^[a-zA-Z0-9_-]{1,100}$/.test(rawId) ? rawId : null;
  const hasError = url.searchParams.has('code');
  if (returned) {
    const debug = url.searchParams.get('debug');
    url.search = '';
    if (debug === '0' || debug === '1') url.searchParams.set('debug', debug);
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
  window.QWER_PAYMENT_RETURN = Object.freeze({ returned, paymentId, hasError });
})();
