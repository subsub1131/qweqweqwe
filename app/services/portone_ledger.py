"""Atomic, single-process order ledger for test payments only."""
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Literal
from pydantic import BaseModel, ConfigDict
from app.schemas.course import Course

class Order(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    payment_id: str
    owner: str
    course: Course
    store_id: str
    channel_key: str
    status: Literal['PENDING', 'PAID', 'FAILED', 'CANCELLED'] = 'PENDING'

class OrderLedger:
    def __init__(self, path):
        self.path = Path(path).resolve()
        public = Path(__file__).resolve().parents[2] / 'web'
        if self.path == public or public in self.path.parents:
            raise ValueError('Order ledger must not be public.')
        self.lock = RLock()
        self.orders = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict) or raw.get('version') != 1:
                raise ValueError('Unsupported ledger version.')
            orders = [Order.model_validate(item) for item in raw['orders']]
            self.orders = {order.payment_id: order for order in orders}
            if len(self.orders) != len(orders):
                raise ValueError('Duplicate order identity.')

    def save(self, order):
        # Caller holds lock; publish the in-memory update only after durable replacement.
        updated = {**self.orders, order.payment_id: order}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.orders-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as target:
                json.dump({'version': 1, 'orders': [item.model_dump() for item in updated.values()]}, target, ensure_ascii=False)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.orders = updated
