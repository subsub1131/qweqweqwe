"""PortOne V2 test-only order creation and authoritative status synchronization."""
import asyncio
from functools import lru_cache
from uuid import uuid4
from threading import RLock
from fastapi import HTTPException
from portone_server_sdk import webhook
import httpx
from urllib.parse import quote
from app.services.portone_snapshot import normalize_payment
from app.core.config import settings
from app.services.portone_ledger import Order, OrderLedger

class PaymentService:
    def __init__(self, order_file, *, lookup=None):
        self.order_file = order_file
        self._ledger = None
        self._ledger_lock = RLock()
        self.lookup = lookup

    @property
    def ledger(self):
        with self._ledger_lock:
            if self._ledger is None:
                try:
                    self._ledger = OrderLedger(self.order_file)
                except (OSError, ValueError, KeyError, TypeError):
                    raise HTTPException(status_code=503, detail='Payment ledger unavailable.') from None
            return self._ledger

    def require_enabled(self):
        if not settings.portone_enabled():
            raise HTTPException(status_code=503, detail='Test payments are not configured.')

    def create(self, owner, course):
        self.require_enabled()
        if course.price <= 0:
            raise HTTPException(status_code=422, detail='A positive course price is required.')
        with self.ledger.lock:
            for order in self.ledger.orders.values():
                if order.owner == owner and order.course.id == course.id:
                    if order.status == 'PAID':
                        raise HTTPException(status_code=409, detail='Course already purchased.')
                    if order.status == 'PENDING' and order.store_id == settings.PORTONE_STORE_ID and order.channel_key == settings.PORTONE_CHANNEL_KEY:
                        return order
            order = Order(payment_id=str(uuid4()), owner=owner, course=course,
                          store_id=settings.PORTONE_STORE_ID, channel_key=settings.PORTONE_CHANNEL_KEY)
            self.ledger.save(order)
            return order

    def checkout(self, order):
        return {'storeId': order.store_id, 'channelKey': order.channel_key,
                'paymentId': order.payment_id, 'orderName': order.course.title,
                'totalAmount': order.course.price, 'currency': 'CURRENCY_KRW', 'payMethod': 'CARD',
                'redirectUrl': settings.FRONTEND_URL.rstrip('/') + '/courses.html?payment_return=1'}

    def own_order(self, payment_id, owner):
        with self.ledger.lock:
            order = self.ledger.orders.get(payment_id)
            if order is None or order.owner != owner:
                raise HTTPException(status_code=404, detail='Order not found.')
            return order

    async def lookup_payment(self, *, payment_id):
        # The SDK client does not expose transport cleanup. Scope this read-only REST
        # request so success, errors, timeouts and cancellation all close the client.
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                'https://api.portone.io/payments/' + quote(payment_id, safe=''),
                headers={'Authorization': 'PortOne ' + settings.PORTONE_API_SECRET},
                params={'storeId': settings.PORTONE_STORE_ID},
            )
            response.raise_for_status()
            return response.json()

    async def sync(self, payment_id):
        self.require_enabled()
        with self.ledger.lock:
            order = self.ledger.orders.get(payment_id)
        if order is None:
            return None
        try:
            lookup = self.lookup or self.lookup_payment
            result = await asyncio.wait_for(lookup(payment_id=payment_id), timeout=10)
            payment = normalize_payment(result)
        except Exception:
            raise HTTPException(status_code=503, detail='Payment lookup unavailable. Retry later.') from None
        channel = getattr(payment, 'channel', None)
        amount = getattr(payment, 'amount', None)
        if (getattr(payment, 'id', None) != order.payment_id
                or getattr(payment, 'store_id', None) != order.store_id
                or order.store_id != settings.PORTONE_STORE_ID
                or order.channel_key != settings.PORTONE_CHANNEL_KEY
                or getattr(channel, 'type', None) != 'TEST'
                or getattr(channel, 'key', None) != order.channel_key
                or getattr(payment, 'currency', None) != 'KRW'
                or getattr(amount, 'total', None) != order.course.price):
            raise HTTPException(status_code=409, detail='Payment verification failed.')
        if payment.status in {'CANCELLED', 'PARTIAL_CANCELLED'} or amount.cancelled > 0:
            status = 'CANCELLED'
        elif payment.status == 'PAID':
            if amount.paid != order.course.price or amount.cancelled != 0:
                raise HTTPException(status_code=409, detail='Payment verification failed.')
            status = 'PAID'
        elif payment.status == 'FAILED':
            status = 'FAILED'
        else:
            status = 'PENDING'
        with self.ledger.lock:
            current = self.ledger.orders[payment_id]
            # Cancellation is terminal, including when a stale API request finishes later.
            if current.status == 'CANCELLED':
                return current
            if current.status == 'PAID' and status in {'PENDING', 'FAILED'}:
                return current
            updated = current.model_copy(update={'status': status})
            self.ledger.save(updated)
            return updated

    def restore_catalog(self, repository):
        with self.ledger.lock:
            repository.restore_snapshots([order.course for order in self.ledger.orders.values()])

    def purchased_courses(self, owner):
        self.require_enabled()
        with self.ledger.lock:
            courses = {order.course.id: order.course for order in self.ledger.orders.values()
                       if order.owner == owner and order.status == 'PAID'}
            return list(courses.values())

    async def handle_webhook(self, raw, headers):
        self.require_enabled()
        try:
            event = webhook.verify(settings.PORTONE_WEBHOOK_SECRET, raw.decode('utf-8'), headers)
        except webhook.InvalidInputError:
            raise HTTPException(status_code=503, detail='Webhook is not configured.') from None
        except (webhook.WebhookVerificationError, ValueError, TypeError, KeyError):
            raise HTTPException(status_code=400, detail='Invalid webhook.') from None
        # SDK leaves unknown event types as dicts. Only typed transaction events trigger lookup.
        if isinstance(event, dict):
            return
        data = getattr(event, 'data', None)
        payment_id = getattr(data, 'payment_id', None)
        if not payment_id:
            return
        await self.sync(payment_id)

@lru_cache(maxsize=1)
def _default_service(order_file):
    return PaymentService(order_file)

def get_payment_service():
    try:
        return _default_service(settings.PORTONE_ORDER_FILE)
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=503, detail='Payment ledger unavailable.') from None
