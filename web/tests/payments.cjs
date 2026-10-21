const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/subsu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req,res) => {
  const file = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(file, (err,data) => { res.writeHead(err ? 404 : 200, {'Content-Type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html'}); res.end(err ? 'Missing' : data); });
});
(async () => {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const base='http://127.0.0.1:'+server.address().port;
  try {
    async function scenario(options={}) {
      const page=await browser.newPage();
      const calls=[],logs=[];
      page.on('console',msg=>logs.push(msg.text()));
      page.on('pageerror',error=>{throw error;});
      let auth=options.auth!==false, confirmStatus=options.status||'PAID', networkFail=false, sdkLoads=0;
      const course={id:1,title:'첫 수업',description:'작은 배움',category:'취미',price:19000,duration_minutes:60,lesson_count:4,instructor:'봄 선생님'};
      const checkout={storeId:'store-test',channelKey:'channel-test',paymentId:'payment-test-1',orderName:course.title,totalAmount:19000,currency:'CURRENCY_KRW',payMethod:'CARD',redirectUrl:base+'/courses.html?payment_return=1'};
      if(!['load-failure','timeout','cdn'].includes(options.sdk))await page.addInitScript(({kind})=>{window.sdkCalls=[];window.PortOne={requestPayment:async checkout=>{window.sdkCalls.push(checkout);if(kind==='overlay'){const frame=document.createElement('iframe');frame.id='test-pg-frame';frame.title='테스트 결제창';frame.style.cssText='position:fixed;inset:0;width:100vw;height:100vh;z-index:2147483647;background:white';document.body.append(frame);return new Promise(resolve=>{window.finishTestPayment=()=>{frame.remove();resolve({code:'CANCEL'});};});}if(kind==='cancel')return {code:'FAILURE_TYPE_PG',message:'RAW_SENSITIVE_ERROR',pgMessage:'RAW_PG_MESSAGE'};if(kind==='throw')throw Error('RAW_SENSITIVE_ERROR');if(kind==='undefined')return undefined;return {paymentId:checkout.paymentId};}};},{kind:options.sdk});
      await page.route('https://cdn.portone.io/v2/browser-sdk.js',async route=>{sdkLoads++;if(options.sdk==='cdn')await route.fulfill({contentType:'text/javascript',body:'window.sdkCalls=[];window.PortOne={requestPayment:async checkout=>{window.sdkCalls.push(checkout);return {paymentId:checkout.paymentId};}};'});else if(options.sdk!=='timeout')await route.abort();});
      await page.route('http://127.0.0.1:8000/api/**',async route=>{
        const req=route.request(),pathname=new URL(req.url()).pathname;
        calls.push({path:pathname,body:req.postDataJSON(),headers:req.headers()});
        let status=200,body;
        if(pathname==='/api/courses')body={items:[course]};
        else if(pathname==='/api/courses/1')body=course;
        else if(pathname==='/api/payments/config')body={enabled:options.enabled!==false,mode:'portone-test'};
        else if(pathname==='/api/payments/orders'){status=auth?(options.orderHttpStatus||200):401;body=auth?{payment_id:checkout.paymentId,status:'PENDING',checkout,course}:{detail:'Unauthorized'};}
        else if(pathname==='/api/payments/confirm'){if(networkFail)return route.abort();status=auth?(options.confirmHttpStatus||200):401;body=auth?{payment_id:checkout.paymentId,status:confirmStatus}:{detail:'Unauthorized'};}
        else if(pathname==='/api/my/courses')body={items:confirmStatus==='PAID'?[course]:[]};
        else if(pathname==='/api/demo/purchases')throw Error('Legacy mock purchase must never be used');
        else throw Error('Unexpected request '+pathname);
        await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
      });
      const url=options.returned?base+'/courses.html?debug=1&payment_return=1&paymentId=payment-test-1&message=RAW_SENSITIVE_ERROR&pgMessage=RAW_PG_MESSAGE&pgCode=RAW_PG_CODE&txId=RAW_TRANSACTION&transactionType=RAW_TYPE'+(options.returnError?'&code=CANCEL':''):base+'/courses.html?debug=1';
      await page.goto(url);
      await page.locator('[data-testid=course-detail]').click();
      return {page,calls,logs,checkout,get sdkLoads(){return sdkLoads;},setAuth:value=>auth=value,setStatus:value=>confirmStatus=value,setNetwork:value=>networkFail=value};
    }
    const disabled=await scenario({enabled:false});
    await disabled.page.getByTestId('purchase-button').click();
    await disabled.page.getByTestId('detail-message').filter({hasText:'설정'}).waitFor({timeout:2500});
    assert.equal(disabled.calls.filter(c=>c.path.endsWith('/orders')).length,0);
    assert.equal(await disabled.page.evaluate(()=>window.sdkCalls.length),0);
    assert.equal(disabled.sdkLoads,0);
    await disabled.page.close();

    const overlay=await scenario({sdk:'overlay'});
    await overlay.page.getByTestId('purchase-button').click();
    await overlay.page.locator('#test-pg-frame').waitFor();
    assert.equal(await overlay.page.locator('#course-dialog').evaluate(dialog=>dialog.open),false);
    assert.equal(await overlay.page.evaluate(()=>document.elementFromPoint(innerWidth/2,innerHeight/2)?.id),'test-pg-frame');
    await overlay.page.evaluate(()=>window.finishTestPayment());
    await overlay.page.getByTestId('detail-message').filter({hasText:'취소'}).waitFor();
    assert.equal(await overlay.page.locator('#course-dialog').evaluate(dialog=>dialog.open),true);
    await overlay.page.close();

    const paid=await scenario();
    await paid.page.getByTestId('purchase-button').click();
    await paid.page.getByTestId('detail-message').filter({hasText:'완료'}).waitFor();
    assert.deepEqual(await paid.page.evaluate(()=>window.sdkCalls[0]),paid.checkout);
    assert.deepEqual(paid.calls.find(c=>c.path.endsWith('/orders')).body,{course_id:1});
    assert.deepEqual(paid.calls.find(c=>c.path.endsWith('/confirm')).body,{payment_id:'payment-test-1'});
    assert.ok(paid.calls.every(c=>c.headers['x-request-id']));
    assert.ok(paid.calls.every(c=>!c.headers.referer));
    assert.equal(await paid.page.evaluate(()=>sessionStorage.getItem('qwer.pendingPayment')),null);
    await paid.page.close();

    const verificationConflict=await scenario({confirmHttpStatus:409});
    await verificationConflict.page.getByTestId('purchase-button').click();
    await verificationConflict.page.getByTestId('detail-message').filter({hasText:'검증'}).waitFor({timeout:2500});
    const conflictMessage=await verificationConflict.page.getByTestId('detail-message').innerText();
    assert.ok(!conflictMessage.includes('이미 구매'));
    assert.ok(!conflictMessage.includes('확인 완료'));
    assert.ok(await verificationConflict.page.locator('#detail-payment-retry').isVisible());
    assert.equal(await verificationConflict.page.evaluate(()=>sessionStorage.getItem('qwer.pendingPayment')),'payment-test-1');
    await verificationConflict.page.close();
    const owned=await scenario({orderHttpStatus:409});
    await owned.page.getByTestId('purchase-button').click();
    await owned.page.getByTestId('detail-message').filter({hasText:'이미 구매'}).waitFor();
    assert.equal(await owned.page.evaluate(()=>window.sdkCalls.length),0);
    await owned.page.close();

    const cdn=await scenario({sdk:'cdn'});
    await cdn.page.getByTestId('purchase-button').click();
    await cdn.page.getByTestId('detail-message').filter({hasText:'완료'}).waitFor();
    assert.equal(cdn.sdkLoads,1);
    assert.deepEqual(await cdn.page.evaluate(()=>window.sdkCalls[0]),cdn.checkout);
    await cdn.page.close();

    for(const sdk of ['cancel','throw','undefined','load-failure','timeout']) {
      const test=await scenario({sdk});
      if(sdk==='timeout')await test.page.clock.install();
      await test.page.getByTestId('purchase-button').click();
      if(sdk==='timeout'){await test.page.waitForFunction(()=>document.querySelector('script[src="https://cdn.portone.io/v2/browser-sdk.js"]'));await test.page.clock.fastForward(12001);}
      const expected=['load-failure','timeout'].includes(sdk)?'불러오지':sdk==='undefined'?'이동':'취소';
      await test.page.getByTestId('detail-message').filter({hasText:expected}).waitFor();
      assert.equal(test.calls.filter(c=>c.path.endsWith('/confirm')).length,0);
      assert.ok(!(await test.page.locator('body').innerText()).includes('RAW_'));
      assert.ok(!test.logs.join('').includes('RAW_'));
      await test.page.close();
    }
    const pending=await scenario({status:'PENDING'});
    await pending.page.getByTestId('purchase-button').click();
    await pending.page.getByTestId('detail-message').filter({hasText:'잠시 후 다시 확인'}).waitFor();
    assert.ok(!(await pending.page.getByTestId('detail-message').innerText()).includes('확인 완료'));
    assert.ok(await pending.page.locator('#detail-payment-retry').isVisible());
    if(process.env.PAYMENT_SCREENSHOT)await pending.page.screenshot({path:process.env.PAYMENT_SCREENSHOT,fullPage:true});
    await pending.page.getByRole('button',{name:'닫기',exact:true}).click();
    pending.setNetwork(true);
    await pending.page.getByTestId('payment-retry').click();
    await pending.page.getByTestId('payment-message').filter({hasText:'연결'}).waitFor();
    pending.setNetwork(false);pending.setStatus('PAID');
    await pending.page.getByTestId('payment-retry').click();
    await pending.page.getByTestId('payment-message').filter({hasText:'완료'}).waitFor();
    await pending.page.close();

    for(const [status,expected] of [['CANCELLED','취소된'],['FAILED','실패']]) {
      const terminal=await scenario({status});
      await terminal.page.getByTestId('purchase-button').click();
      await terminal.page.getByTestId('detail-message').filter({hasText:expected}).waitFor();
      assert.ok(!(await terminal.page.getByTestId('detail-message').innerText()).includes('확인 완료'));
      await terminal.page.close();
    }
    const cancelledReturn=await scenario({returned:true,returnError:true});
    await cancelledReturn.page.getByTestId('payment-message').filter({hasText:'취소'}).waitFor();
    assert.equal(new URL(cancelledReturn.page.url()).search,'?debug=1');
    assert.equal(cancelledReturn.calls.filter(c=>c.path.endsWith('/confirm')).length,0);
    assert.ok(!cancelledReturn.logs.join('').includes('RAW_'));
    await cancelledReturn.page.close();
    const returned=await scenario({returned:true,auth:false});
    await returned.page.getByTestId('payment-message').filter({hasText:'로그인'}).waitFor();
    assert.equal(new URL(returned.page.url()).search,'?debug=1');
    assert.ok(!returned.logs.join('').includes('RAW_'));
    assert.equal(await returned.page.evaluate(()=>sessionStorage.getItem('qwer.pendingPayment')),'payment-test-1');
    await returned.page.getByRole('button',{name:'닫기',exact:true}).click();
    returned.setAuth(true);
    await returned.page.getByTestId('payment-retry').click();
    await returned.page.getByTestId('payment-message').filter({hasText:'완료'}).waitFor();
    await returned.page.close();
    console.log('PASS: disabled config, server checkout, lazy CDN load, PAID confirmation, operation-aware 409, SDK cancel/throw/undefined/load failure/timeout, cancelled/failed, pending/network retry, mobile query cleanup/auth retry');
  } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
