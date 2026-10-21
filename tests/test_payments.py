"""PortOne test-only payment contracts. No external gateway calls."""
import base64
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from tests import test_auth as fixture
from portone_server_sdk.payment import PaidPayment, CancelledPayment, PaymentAmount
from portone_server_sdk.common import SelectedChannel

SECRET = b'test-webhook-secret-32-bytes-long!'
CONFIG = dict(PORTONE_ENABLED=True, PORTONE_STORE_ID='store-test', PORTONE_CHANNEL_KEY='channel-test', PORTONE_API_SECRET='api-test', PORTONE_WEBHOOK_SECRET=base64.b64encode(SECRET).decode())

class PaymentTests(unittest.TestCase):
    tearDown = fixture.AuthTests.tearDown
    seed_local_user = fixture.AuthTests.seed_local_user
    login = fixture.AuthTests.login
    origin = {'Origin': 'http://localhost:8080'}

    def setUp(self):
        fixture.AuthTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'orders.json'
        self.lookup = AsyncMock()
        from app.services.portone import PaymentService, get_payment_service
        self.settings_patch = patch.multiple(fixture.settings, **CONFIG)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.service = PaymentService(self.file, lookup=self.lookup)
        fixture.app.dependency_overrides[get_payment_service] = lambda: self.service
        self.seed_local_user()
        self.assertEqual(self.login().status_code, 200)

    def order(self):
        response = self.client.post('/api/payments/orders', json={'course_id': 1}, headers=self.origin)
        self.assertEqual(response.status_code, 201)
        return response.json()

    def paid(self, payment_id, **changes):
        payment = object.__new__(PaidPayment)
        payment.id = payment_id
        payment.store_id = 'store-test'
        payment.channel = SelectedChannel(type='TEST', pg_provider='INICIS_V2', pg_merchant_id='test', key='channel-test')
        payment.currency = 'KRW'
        payment.amount = PaymentAmount(total=39000, paid=39000, cancelled=0, tax_free=0, discount=0, cancelled_tax_free=0)
        for key, value in changes.items():
            setattr(payment, key, value)
        return payment

    def confirm(self, payment_id):
        return self.client.post('/api/payments/confirm', json={'payment_id': payment_id}, headers=self.origin)

    def hook(self, payment_id, event='Transaction.Paid', timestamp=None, valid=True):
        body = json.dumps({'type': event, 'timestamp': '2026-10-20T00:00:00Z', 'data': {'paymentId': payment_id, 'storeId': 'store-test', 'transactionId': 'transaction-test', 'cancellationId': 'cancel-test'}})
        stamp = str(timestamp if timestamp is not None else int(time.time()))
        signature = base64.b64encode(hmac.digest(SECRET, f'msg-test.{stamp}.{body}'.encode(), 'sha256')).decode()
        return self.client.post('/api/payments/webhook', content=body, headers={'webhook-id': 'msg-test', 'webhook-timestamp': stamp, 'webhook-signature': 'v1,' + (signature if valid else 'AAAA')})

    def test_config_and_order_snapshot_reuse(self):
        self.assertEqual(self.client.get('/api/payments/config').json(), {'enabled': True, 'mode': 'portone-test'})
        first = self.order()
        self.assertEqual(first['status'], 'PENDING')
        self.assertEqual(first['checkout']['totalAmount'], 39000)
        self.assertEqual(first['checkout']['redirectUrl'], 'http://localhost:8080/courses.html?payment_return=1')
        self.assertEqual(self.order()['payment_id'], first['payment_id'])
        self.assertNotIn('api-test', self.file.read_text(encoding='utf-8'))
        self.assertEqual(self.client.post('/api/demo/purchases', json={'course_id': 1}, headers=self.origin).status_code, 403)

    def test_paid_confirmation_and_restart_recovery(self):
        order = self.order()
        self.lookup.return_value = self.paid(order['payment_id'])
        self.assertEqual(self.confirm(order['payment_id']).json()['status'], 'PAID')
        self.assertEqual(self.client.get('/api/my/courses').json()['items'], [order['course']])
        self.assertEqual(self.client.post('/api/payments/orders', json={'course_id': 1}, headers=self.origin).status_code, 409)
        from app.services.portone import PaymentService
        self.service = PaymentService(self.file, lookup=self.lookup)
        self.assertEqual(self.client.get('/api/my/courses').json()['items'], [order['course']])

    def test_mismatched_verified_payment_cannot_grant(self):
        order = self.order()
        variants = [dict(id='foreign'), dict(store_id='foreign'), dict(currency='USD'), dict(channel=SelectedChannel(type='LIVE', pg_provider='INICIS_V2', pg_merchant_id='test', key='channel-test')), dict(channel=SelectedChannel(type='TEST', pg_provider='INICIS_V2', pg_merchant_id='test', key='foreign')), dict(amount=PaymentAmount(total=1, paid=1, cancelled=0, tax_free=0, discount=0, cancelled_tax_free=0)), dict(amount=PaymentAmount(total=39000, paid=1, cancelled=0, tax_free=0, discount=0, cancelled_tax_free=0))]
        for change in variants:
            with self.subTest(change=change):
                self.lookup.return_value = self.paid(order['payment_id'], **change)
                self.assertNotEqual(self.confirm(order['payment_id']).json().get('status'), 'PAID')
                self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})

    def test_signed_duplicate_webhook_and_cancel_is_terminal(self):
        order = self.order()
        self.lookup.return_value = self.paid(order['payment_id'])
        self.assertEqual(self.hook(order['payment_id']).status_code, 200)
        self.assertEqual(self.hook(order['payment_id']).status_code, 200)
        self.assertEqual(len(self.client.get('/api/my/courses').json()['items']), 1)
        cancelled = object.__new__(CancelledPayment)
        cancelled.id = order['payment_id']; cancelled.store_id = 'store-test'
        cancelled.channel = self.paid(order['payment_id']).channel
        cancelled.currency = 'KRW'; cancelled.amount = PaymentAmount(total=39000, paid=0, cancelled=39000, tax_free=0, discount=0, cancelled_tax_free=0)
        self.lookup.return_value = cancelled
        self.assertEqual(self.hook(order['payment_id'], 'Transaction.Cancelled').status_code, 200)
        self.lookup.return_value = self.paid(order['payment_id'])
        self.assertEqual(self.hook(order['payment_id']).status_code, 200)
        self.assertEqual(self.confirm(order['payment_id']).json()['status'], 'CANCELLED')
        self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})

    def test_invalid_or_replayed_webhook_rejected_unknown_ignored(self):
        order = self.order()
        self.assertEqual(self.hook(order['payment_id'], valid=False).status_code, 400)
        self.assertEqual(self.hook(order['payment_id'], timestamp=int(time.time()) - 600).status_code, 400)
        self.assertEqual(self.hook(order['payment_id'], timestamp=int(time.time()) + 600).status_code, 400)
        self.assertEqual(self.hook('unknown-order').status_code, 200)
        self.assertEqual(self.hook(order['payment_id'], event='Unknown.Event').status_code, 200)
        self.lookup.assert_not_awaited()
        self.assertEqual(self.client.post('/api/payments/webhook', content=b'x' * 65537).status_code, 413)

    def test_timeout_retries_and_foreign_order_hidden(self):
        order = self.order()
        self.lookup.side_effect = TimeoutError()
        self.assertEqual(self.confirm(order['payment_id']).status_code, 503)
        self.assertEqual(self.hook(order['payment_id']).status_code, 503)
        self.lookup.side_effect = None
        self.lookup.return_value = self.paid(order['payment_id'])
        self.assertEqual(self.confirm(order['payment_id']).json()['status'], 'PAID')
        self.seed_local_user(user_id='other')
        self.client.post('/user/login', json={'userId': 'other', 'userPwd': 'correct-password'})
        self.assertEqual(self.confirm(order['payment_id']).status_code, 404)
        self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})

    def test_disabled_missing_config_and_mutation_guards(self):
        for change in ({'PORTONE_ENABLED': False}, {'PORTONE_WEBHOOK_SECRET': ''}):
            with patch.multiple(fixture.settings, **change):
                self.assertFalse(self.client.get('/api/payments/config').json()['enabled'])
                self.assertEqual(self.client.post('/api/payments/orders', json={'course_id': 1}, headers=self.origin).status_code, 503)
        for path, data in (('/api/payments/orders', {'course_id': 1}), ('/api/payments/confirm', {'payment_id': 'unknown'})):
            self.assertEqual(self.client.post(path, json=data).status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.client.post('/api/payments/orders', json={'course_id': 1}, headers=self.origin).status_code, 401)

    def test_custom_course_snapshot_restored_before_id_allocation(self):
        from api.routers import courses
        from app.schemas.course import CourseInput
        from app.services.course_demo import CourseDemoRepository
        from app.services.portone import PaymentService
        with patch.object(courses, 'repository', CourseDemoRepository()):
            course = courses.repository.create(CourseInput(title='Durable custom', description='Snapshot', category='Test', price=12000, duration_minutes=10, lesson_count=1))
            response = self.client.post('/api/payments/orders', json={'course_id': course.id}, headers=self.origin)
            self.assertEqual(response.status_code, 201)
            self.service = PaymentService(self.file, lookup=self.lookup)
            courses.repository = CourseDemoRepository()
            restored = self.client.get('/api/courses/5')
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()['title'], 'Durable custom')
            new = self.client.post('/api/demo/courses', json={'title': 'Another', 'description': 'New', 'category': 'Test', 'price': 1000, 'duration_minutes': 10, 'lesson_count': 1}, headers=self.origin)
            self.assertEqual(new.json()['id'], 6)
    def test_pending_and_partial_cancel_never_grant(self):
        from portone_server_sdk.payment import ReadyPayment, PartialCancelledPayment
        order = self.order()
        ready = object.__new__(ReadyPayment)
        paid = self.paid(order['payment_id'])
        for key in ('id', 'store_id', 'channel', 'currency', 'amount'):
            setattr(ready, key, getattr(paid, key))
        self.lookup.return_value = ready
        self.assertEqual(self.confirm(order['payment_id']).json()['status'], 'PENDING')
        self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})
        partial = object.__new__(PartialCancelledPayment)
        for key in ('id', 'store_id', 'channel', 'currency'):
            setattr(partial, key, getattr(paid, key))
        partial.amount = PaymentAmount(total=39000, paid=38000, cancelled=1000, tax_free=0, discount=0, cancelled_tax_free=0)
        self.lookup.return_value = partial
        self.assertEqual(self.confirm(order['payment_id']).json()['status'], 'CANCELLED')
        self.lookup.return_value = paid
        self.assertEqual(self.confirm(order['payment_id']).json()['status'], 'CANCELLED')
        self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})

    def test_concurrent_stale_paid_cannot_restore_cancelled_access(self):
        import asyncio
        order = self.order()
        payment_id = order['payment_id']
        paid = self.paid(payment_id)
        cancelled = object.__new__(CancelledPayment)
        for key in ('id', 'store_id', 'channel', 'currency'):
            setattr(cancelled, key, getattr(paid, key))
        cancelled.amount = PaymentAmount(total=39000, paid=0, cancelled=39000, tax_free=0, discount=0, cancelled_tax_free=0)
        async def race():
            started, release = asyncio.Event(), asyncio.Event()
            calls = 0
            async def lookup(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    started.set()
                    await release.wait()
                    return paid
                return cancelled
            self.service.lookup = lookup
            stale = asyncio.create_task(self.service.sync(payment_id))
            await started.wait()
            result = await self.service.sync(payment_id)
            self.assertEqual(result.status, 'CANCELLED')
            release.set()
            self.assertEqual((await stale).status, 'CANCELLED')
        asyncio.run(race())
        self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})

    def test_orders_reject_free_and_client_overrides(self):
        from api.routers import courses
        from app.schemas.course import CourseInput
        from app.services.course_demo import CourseDemoRepository
        with patch.object(courses, 'repository', CourseDemoRepository()):
            free = courses.repository.create(CourseInput(title='Free', description='Free', category='Test', price=0, duration_minutes=10, lesson_count=1))
            self.assertEqual(self.client.post('/api/payments/orders', json={'course_id': free.id}, headers=self.origin).status_code, 422)
        for body in ({'course_id': 1, 'price': 0}, {'course_id': 1, 'owner': 'other'}, {'course_id': True}):
            self.assertEqual(self.client.post('/api/payments/orders', json=body, headers=self.origin).status_code, 422)
        self.assertEqual(self.client.post('/api/payments/confirm', json={'payment_id': 'unknown', 'status': 'PAID'}, headers=self.origin).status_code, 422)
    def test_disabled_payments_do_not_load_payment_ledger(self):
        from app.services.portone import get_payment_service
        self.file.write_text('invalid ledger', encoding='utf-8')
        fixture.app.dependency_overrides.pop(get_payment_service)
        with patch.multiple(fixture.settings, PORTONE_ENABLED=False, PORTONE_ORDER_FILE=str(self.file)):
            self.assertEqual(self.client.get('/api/courses').status_code, 200)
            self.assertEqual(self.client.get('/api/my/courses').status_code, 200)
    def test_rest_lookup_auth_url_and_client_closed(self):
        import httpx
        order = self.order()
        self.service.lookup = None
        requests, clients = [], []
        real_client = httpx.AsyncClient
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'status': 'PAID', 'id': order['payment_id'], 'storeId': 'store-test', 'channel': {'type': 'TEST', 'key': 'channel-test'}, 'currency': 'KRW', 'amount': {'total': 39000, 'paid': 39000, 'cancelled': 0}})
        def create_client(**kwargs):
            client = real_client(transport=httpx.MockTransport(handler), **kwargs)
            clients.append(client)
            return client
        with patch('httpx.AsyncClient', side_effect=create_client):
            response = self.confirm(order['payment_id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'PAID')
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.host, 'api.portone.io')
        self.assertEqual(requests[0].url.path, '/payments/' + order['payment_id'])
        self.assertEqual(requests[0].url.params['storeId'], 'store-test')
        self.assertEqual(requests[0].headers['authorization'], 'PortOne api-test')
        self.assertTrue(clients)
        self.assertTrue(all(client.is_closed for client in clients))

    def test_rest_failure_closes_client_without_raw_error(self):
        import httpx
        order = self.order()
        self.service.lookup = None
        clients = []
        real_client = httpx.AsyncClient
        def handler(request):
            raise httpx.ReadTimeout('private-provider-error api-test', request=request)
        def create_client(**kwargs):
            client = real_client(transport=httpx.MockTransport(handler), **kwargs)
            clients.append(client)
            return client
        with patch('httpx.AsyncClient', side_effect=create_client):
            response = self.confirm(order['payment_id'])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-provider-error', response.text)
        self.assertNotIn('api-test', response.text)
        self.assertTrue(clients)
        self.assertTrue(all(client.is_closed for client in clients))
    def test_non_object_ledger_returns_safe_unavailable(self):
        from app.services.portone import PaymentService
        self.file.write_text('[]', encoding='utf-8')
        self.service = PaymentService(self.file, lookup=self.lookup)
        response = self.client.get('/api/my/courses')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('AttributeError', response.text)
    def test_atomic_replace_failure_does_not_publish_paid_access(self):
        order = self.order()
        self.lookup.return_value = self.paid(order['payment_id'])
        with patch('app.services.portone_ledger.os.replace', side_effect=OSError('private-filesystem-error')):
            response = self.confirm(order['payment_id'])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-filesystem-error', response.text)
        self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})
        from app.services.portone import PaymentService
        recovered = PaymentService(self.file, lookup=self.lookup)
        self.assertEqual(recovered.ledger.orders[order['payment_id']].status, 'PENDING')

    def test_raw_response_requires_strict_amount_and_known_status(self):
        order = self.order()
        body = {'status': 'PAID', 'id': order['payment_id'], 'storeId': 'store-test', 'channel': {'type': 'TEST', 'key': 'channel-test'}, 'currency': 'KRW', 'amount': {'total': 39000, 'paid': 39000, 'cancelled': 0}}
        for change in ({'status': 'UNKNOWN'}, {'amount': {'total': '39000', 'paid': 39000, 'cancelled': 0}}, {'amount': {'total': 39000, 'paid': True, 'cancelled': 0}}):
            self.lookup.return_value = {**body, **change}
            self.assertEqual(self.confirm(order['payment_id']).status_code, 503)
            self.assertEqual(self.client.get('/api/my/courses').json(), {'items': []})
