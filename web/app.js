(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = $('auth-form');
  const password = $('user-password');
  const apiBaseUrl = window.QWER_CONFIG.apiBaseUrl.replace(/\/$/, '');
  let debugEnabled = false;
  try {
    const debug = new URLSearchParams(window.location.search).get('debug');
    if (debug === '1') sessionStorage.setItem('qwer.debug', '1');
    if (debug === '0') sessionStorage.removeItem('qwer.debug');
    debugEnabled = sessionStorage.getItem('qwer.debug') === '1';
  } catch { /* Diagnostics must not prevent login when storage is blocked. */ }

  function trace(metadata) {
    if (debugEnabled) console.info('[qwer:http]', metadata);
  }
  const callbackMessages = {
    kakao_cancelled: '카카오 로그인이 취소되었어요. 원하실 때 다시 시작해 주세요.',
    invalid_state: '로그인 확인 시간이 지났거나 요청을 확인할 수 없어요. 다시 시작해 주세요.',
    kakao_unavailable: '지금은 카카오 로그인을 이용할 수 없어요. 잠시 후 다시 시도해 주세요.',
    kakao_failed: '카카오 로그인을 완료하지 못했어요. 잠시 후 다시 시도해 주세요.'
  };
  let mode = 'login';
  let pending = false;
  let sessionReady = false;
  let kakaoReady = false;

  class RequestError extends Error {
    constructor(message, status = 0) { super(message); this.status = status; }
  }

  async function request(path, options = {}) {
    const requestId = crypto.randomUUID();
    const started = performance.now();
    let responseId = requestId, status = 0, outcome = 'network_error';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${apiBaseUrl}${path}`, {
        ...options,
        credentials: 'include',
        cache: 'no-store',
        headers: { 'Accept': 'application/json', 'X-Request-ID': requestId, ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
        signal: controller.signal
      });
      status = response.status;
      const returnedId = response.headers.get('X-Request-ID');
      if (/^[0-9a-f-]{36}$/i.test(returnedId || '')) responseId = returnedId;
      outcome = response.ok ? 'success' : 'http_error';
      const text = await response.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { /* Raw server pages never become product messages. */ }
      if (!response.ok) {
        let message = '요청을 완료하지 못했어요. 잠시 후 다시 시도해 주세요.';
        if (response.status === 401) message = '아이디 또는 비밀번호를 확인해 주세요.';
        else if (response.status === 409) message = '이미 사용 중인 아이디예요. 다른 아이디를 입력해 주세요.';
        else if (response.status === 403) message = '요청을 확인할 수 없어요. 화면을 새로고침한 뒤 다시 시도해 주세요.';
        else if (response.status === 422) message = '입력 정보를 확인해 주세요.';
        else if (response.status < 500 && typeof data?.detail === 'string' && /[가-힣]/.test(data.detail)) message = data.detail;
        throw new RequestError(message, response.status);
      }
      if (response.status !== 204 && (!data || typeof data !== 'object')) {
        outcome = 'invalid_response';
        throw new RequestError('응답을 확인하지 못했어요. 잠시 후 다시 시도해 주세요.');
      }
      return data;
    } catch (error) {
      if (controller.signal.aborted) {
        outcome = 'timeout';
        throw new RequestError('응답 시간이 길어지고 있어요. 잠시 후 다시 시도해 주세요.');
      }
      if (error instanceof RequestError) throw error;
      throw new RequestError('연결을 확인해 주세요. 잠시 후 다시 시도해 주세요.');
    } finally {
      clearTimeout(timeout);
      trace({ request_id: responseId, method: options.method || 'GET',
        path: new URL(`${apiBaseUrl}${path}`).pathname, status,
        duration_ms: Math.round(performance.now() - started), outcome });
    }
  }

  function message(target, text = '', success = false) {
    $(target).textContent = text;
    $(target).classList.toggle('success', success);
  }

  function syncControls() {
    const locked = pending || !sessionReady;
    $('submit-button').disabled = locked;
    $('mode-button').disabled = locked;
    $('kakao-button').disabled = locked || !kakaoReady;
    $('logout-button').disabled = locked;
    $('password-toggle').disabled = locked;
    form.setAttribute('aria-busy', String(pending));
    for (const input of form.elements) {
      if (input.tagName === 'INPUT') input.disabled = locked || (mode === 'login' && ['userNm', 'email'].includes(input.name));
    }
    $('submit-label').textContent = pending ? '잠시만 기다려 주세요…' : mode === 'login' ? '로그인' : '계정 만들기';
  }

  function hidePassword() {
    password.value = '';
    password.type = 'password';
    $('password-toggle').setAttribute('aria-label', '비밀번호 표시');
    $('password-toggle').setAttribute('aria-pressed', 'false');
  }

  function setMode(next, focus = true) {
    mode = next;
    const signup = mode === 'signup';
    $('signup-fields').hidden = !signup;
    $('social-section').hidden = signup;
    $('form-title').textContent = signup ? '새로운 시작을 함께해요.' : '다시 만나 반가워요.';
    $('form-description').textContent = signup ? '당신만의 공간을 위한 첫걸음이에요.' : '로그인하고 나만의 시간을 이어가세요.';
    $('mode-prompt').textContent = signup ? '이미 계정이 있으신가요?' : '아직 계정이 없으신가요?';
    $('mode-button').textContent = signup ? '로그인으로 돌아가기' : '회원가입';
    password.autocomplete = signup ? 'new-password' : 'current-password';
    password.placeholder = '비밀번호를 입력해 주세요';
    hidePassword();
    message('form-message');
    syncControls();
    if (focus) $('form-title').focus();
  }

  function showProfile(user, focus = false) {
    if (!user || typeof user.userId !== 'string') throw new RequestError('회원 정보를 확인하지 못했어요. 다시 로그인해 주세요.');
    hidePassword();
    $('user-name').value = '';
    $('user-email').value = '';
    const name = typeof user.userNm === 'string' && user.userNm.trim() ? user.userNm : '회원';
    $('profile-name').textContent = name;
    $('profile-avatar').textContent = Array.from(name)[0];
    $('profile-id').textContent = user.userId;
    $('profile-email').textContent = user.email || '';
    $('profile-email-row').hidden = !user.email;
    $('profile-provider').textContent = user.provider === 'kakao' ? '카카오 계정' : '일반 계정';
    $('auth-panel').hidden = true;
    $('profile-panel').hidden = false;
    message('profile-message');
    if (focus) $('profile-title').focus();
  }

  $('mode-button').addEventListener('click', () => { if (!pending && sessionReady) setMode(mode === 'login' ? 'signup' : 'login'); });
  $('password-toggle').addEventListener('click', () => {
    const visible = password.type === 'password';
    password.type = visible ? 'text' : 'password';
    $('password-toggle').setAttribute('aria-label', visible ? '비밀번호 숨기기' : '비밀번호 표시');
    $('password-toggle').setAttribute('aria-pressed', String(visible));
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (pending || !sessionReady || !form.reportValidity()) return;
    const signup = mode === 'signup';
    const payload = { userId: $('user-id').value.trim(), userPwd: password.value };
    if (signup) { payload.userNm = $('user-name').value.trim(); payload.email = $('user-email').value.trim(); }
    pending = true;
    message('form-message');
    syncControls();
    try {
      const user = await request(signup ? '/user/signUp' : '/user/login', { method: 'POST', body: JSON.stringify(payload) });
      if (signup) {
        $('user-name').value = '';
        $('user-email').value = '';
        setMode('login');
        message('form-message', '가입이 완료되었어요. 만든 계정으로 로그인해 주세요.', true);
      } else { showProfile({ ...user, provider: 'local' }, true); message('session-message'); }
    } catch (error) { message('form-message', error.message); }
    finally { pending = false; syncControls(); }
  });

  $('kakao-button').addEventListener('click', () => {
    if (!pending && sessionReady && kakaoReady) {
      trace({ event: 'kakao_navigation', path: '/api/auth/kakao/login' });
      window.location.assign(`${apiBaseUrl}/auth/kakao/login`);
    }
  });
  $('logout-button').addEventListener('click', async () => {
    if (pending) return;
    pending = true;
    syncControls();
    message('profile-message');
    try {
      await request('/auth/logout', { method: 'POST' });
      form.reset();
      $('profile-panel').hidden = true;
      $('auth-panel').hidden = false;
      for (const id of ['profile-name', 'profile-avatar', 'profile-id', 'profile-email', 'profile-provider']) $(id).textContent = '';
      setMode('login');
      message('session-message');
      message('form-message', '안전하게 로그아웃했어요.', true);
    } catch (error) { message('profile-message', error.message); }
    finally { pending = false; syncControls(); }
  });

  const url = new URL(window.location.href);
  if (url.searchParams.has('auth_error')) {
    const error = url.searchParams.get('auth_error');
    if (Object.hasOwn(callbackMessages, error)) message('form-message', callbackMessages[error]);
    url.searchParams.delete('auth_error');
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
  syncControls();
  request('/auth/me').then(user => showProfile(user)).catch(error => {
    if (error.status !== 401) message('session-message', '로그인 상태를 확인하지 못했어요. 연결을 확인하거나 다시 로그인해 주세요.');
  }).finally(() => { sessionReady = true; syncControls(); });
  request('/auth/providers').then(providers => {
    kakaoReady = providers.kakao?.enabled === true;
    $('kakao-note').textContent = kakaoReady ? '' : '카카오 로그인은 준비 중이에요. 일반 계정으로 시작해 주세요.';
  }).catch(() => {
    kakaoReady = false;
    $('kakao-note').textContent = '카카오 로그인 상태를 확인하지 못했어요. 잠시 후 새로고침해 주세요.';
  }).finally(syncControls);
})();

