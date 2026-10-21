export const client = window.axios.create({baseURL: window.QWER_CONFIG.apiBaseUrl.replace(/\/$/, ''), withCredentials: true, timeout:15000, headers:{Accept:'application/json'}});
let debug=false;
try {const value=new URLSearchParams(location.search).get('debug'); if(value==='1') sessionStorage.setItem('qwer.debug','1'); if(value==='0')sessionStorage.removeItem('qwer.debug'); debug=sessionStorage.getItem('qwer.debug')==='1';} catch {}
client.interceptors.request.use(config=>{config.headers['X-Request-ID']=crypto.randomUUID(); config.metadata={started:performance.now(),requestId:config.headers['X-Request-ID']};return config;});
function trace(response, config, outcome) {
  if(!debug || !config)return;
  const returnedId=response?.headers?.['x-request-id'];
  console.info('[qwer:http]',{request_id:/^[0-9a-f-]{36}$/i.test(returnedId||'')?returnedId:config.metadata.requestId,method:config.method.toUpperCase(),path:new URL(config.baseURL+config.url).pathname,status:response?.status||0,duration_ms:Math.round(performance.now()-config.metadata.started),outcome});
}
client.interceptors.response.use(response=>{trace(response,response.config,'success');return response;},error=>{trace(error.response,error.config,error.response?'http_error':error.code==='ECONNABORTED'?'timeout':'network_error');return Promise.reject(error);});
export function errorMessage(error) {
  const status=error.response?.status;
  if(status===401)return '로그인이 필요해요. 로그인 후 다시 시도해 주세요.';
  if(status===403)return '요청을 확인할 수 없어요. 화면을 새로고침해 주세요.';
  if(status===404)return '이 강의를 찾을 수 없어요. 목록을 새로 불러와 주세요.';
  if(status===422)return '입력값을 확인해 주세요. 제목·소개·분류와 숫자 범위를 확인해 주세요.';
  return '연결을 확인하고 잠시 후 다시 시도해 주세요.';
}
export const courseApi={list:()=>client.get('/courses').then(r=>r.data.items),detail:id=>client.get(`/courses/${id}`).then(r=>r.data),register:body=>client.post('/demo/courses',body).then(r=>r.data),mine:()=>client.get('/my/courses').then(r=>r.data.items)};
