const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/subsu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req,res) => {
  const file = path.join(root, req.url.split('?')[0] === '/' ? 'index.html' : decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(file, (err,data) => { res.writeHead(err ? 404 : 200, {'Content-Type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html'}); res.end(err ? 'Missing' : data); });
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true});
  try {
    const page = await browser.newPage();
    await page.addInitScript(()=>{window.PortOne={requestPayment:async checkout=>({paymentId:checkout.paymentId})};});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    let loggedIn = false, purchased = false;
    const courses = Array.from({length:4}, (_,i) => ({id:i+1,title:i===0?'<img src=x onerror=alert(1)>':'봄날의 강의 '+(i+1), description:'차근차근 배우는 첫 수업',category:'취미',price:19000,duration_minutes:90,lesson_count:6,instructor:'봄 선생님'}));
    await page.route('http://127.0.0.1:8000/api/**', async route => {
      const request=route.request(), url=new URL(request.url());
      assert.ok(request.headers()['x-request-id']);
      let status=200, body;
      if(url.pathname==='/api/courses') body={items:courses};
      else if(url.pathname.startsWith('/api/courses/')) body=courses.find(c=>c.id===Number(url.pathname.split('/').pop()));
      else if(url.pathname==='/api/payments/config') body={enabled:true,mode:'portone-test'};
      else if(!loggedIn) {status=401; body={detail:'Login required'};}
      else if(url.pathname==='/api/my/courses') body={items:purchased?[courses[0]]:[]};
      else if(url.pathname==='/api/payments/orders') body={payment_id:'course-test-payment',status:'PENDING',checkout:{paymentId:'course-test-payment'}};
      else if(url.pathname==='/api/payments/confirm') {purchased=true;body={payment_id:'course-test-payment',status:'PAID'};}
      else if(url.pathname==='/api/demo/courses') {status=201;body={...request.postDataJSON(),id:5,instructor:'봄 선생님'};courses.push(body);}
      else throw Error('Unexpected '+url.pathname);
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
    });
    const base='http://127.0.0.1:'+server.address().port;
    await page.goto(base+'/courses.html');
    await page.locator('[data-testid="course-card"]').first().waitFor({timeout:3000});
    assert.equal(await page.locator('[data-testid="course-card"]').count(),4);
    assert.ok(await page.locator('.hero img').evaluate(img=>img.complete && img.naturalWidth>0));
    assert.equal(await page.locator('[data-testid="course-card"] img').count(),0);
    await page.locator('[data-testid="course-detail"]').first().click();
    await page.locator('[data-testid="purchase-button"]').click();
    await page.getByTestId('detail-message').filter({hasText:'로그인'}).waitFor();
    loggedIn=true;
    await page.locator('[data-testid="purchase-button"]').click();
    await page.getByTestId('detail-message').filter({hasText:'완료'}).waitFor();
    await page.getByRole('button',{name:'닫기',exact:true}).click();
    await page.getByTestId('nav-my').click();
    await page.locator('#my-courses [data-testid="course-card"]').waitFor();
    await page.getByTestId('nav-register').click();
    await page.locator('[name="title"]').fill('새 강의');
    await page.locator('[name="description"]').fill('새로운 수업 소개');
    await page.locator('[name="category"]').fill('디자인');
    await page.locator('[name="price"]').fill('25000');
    await page.locator('[name="duration_minutes"]').fill('60');
    await page.locator('[name="lesson_count"]').fill('4');
    await page.getByTestId('register-submit').click();
    await page.getByTestId('register-message').filter({hasText:'등록'}).waitFor();
    await page.getByTestId('nav-catalog').click();
    assert.equal(await page.locator('#course-list [data-testid="course-card"]').count(),5);
    if(process.env.COURSE_DEMO_SCREENSHOT)await page.screenshot({path:process.env.COURSE_DEMO_SCREENSHOT,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(process.env.COURSE_DEMO_SCREENSHOT)await page.screenshot({path:process.env.COURSE_DEMO_SCREENSHOT.replace('.png','-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS: catalog, safe text, login required, confirmed mock payment, my courses, registration, mobile width');
  } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
