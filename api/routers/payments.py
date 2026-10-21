"""Test PG endpoints. Webhooks authenticate through official SDK signature verification."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from api.deps import current_account
from api.routers import courses
from app.core.config import settings
from app.schemas.payment import CreateOrderInput, ConfirmPaymentInput
from app.services.portone import get_payment_service

router = APIRouter(prefix='/api/payments', tags=['test-payments'])

@router.get('/config')
def payment_config(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return {'enabled': settings.portone_enabled(), 'mode': 'portone-test'}

@router.post('/orders', status_code=201, dependencies=[Depends(courses.require_demo_origin)])
def create_order(data: CreateOrderInput, response: Response, identity=Depends(current_account), service=Depends(get_payment_service)):
    service.require_enabled()
    service.restore_catalog(courses.repository)
    course = courses.repository.get(data.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail='Course not found.')
    try:
        order = service.create(courses.owner_key(identity), course)
    except OSError:
        raise HTTPException(status_code=503, detail='Payment ledger unavailable.') from None
    response.headers['Cache-Control'] = 'no-store'
    return {'payment_id': order.payment_id, 'status': order.status, 'checkout': service.checkout(order), 'course': order.course}

@router.post('/confirm', dependencies=[Depends(courses.require_demo_origin)])
async def confirm(data: ConfirmPaymentInput, response: Response, identity=Depends(current_account), service=Depends(get_payment_service)):
    service.require_enabled()
    service.own_order(data.payment_id, courses.owner_key(identity))
    try:
        order = await service.sync(data.payment_id)
    except OSError:
        raise HTTPException(status_code=503, detail='Payment ledger unavailable.') from None
    response.headers['Cache-Control'] = 'no-store'
    return {'payment_id': order.payment_id, 'status': order.status}

@router.post('/webhook')
async def payment_webhook(request: Request, service=Depends(get_payment_service)):
    service.require_enabled()
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 65536:
            raise HTTPException(status_code=413, detail='Webhook body too large.')
        raw.extend(chunk)
    try:
        await service.handle_webhook(bytes(raw), request.headers)
    except OSError:
        raise HTTPException(status_code=503, detail='Payment ledger unavailable.') from None
    return {'ok': True}
