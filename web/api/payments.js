import {client} from './courses.js';
export const paymentApi = {
  config: () => client.get('/payments/config').then(response => response.data),
  order: courseId => client.post('/payments/orders', {course_id: courseId}).then(response => response.data),
  confirm: paymentId => client.post('/payments/confirm', {payment_id: paymentId}).then(response => response.data)
};
let loading;
export function loadPaymentSdk() {
  if (typeof window.PortOne?.requestPayment === 'function') return Promise.resolve(window.PortOne);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.portone.io/v2/browser-sdk.js';
    script.async = true;
    const timer = setTimeout(() => finish(false), 12000);
    function finish(success) {
      clearTimeout(timer);
      script.onload = script.onerror = null;
      if (success && typeof window.PortOne?.requestPayment === 'function') resolve(window.PortOne);
      else { script.remove(); loading = null; reject(new Error('SDK_UNAVAILABLE')); }
    }
    script.onload = () => finish(true);
    script.onerror = () => finish(false);
    document.head.append(script);
  });
  return loading;
}
