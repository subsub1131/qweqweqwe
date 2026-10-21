"""Strict internal payment snapshot shared by REST responses and SDK test doubles."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

class AmountSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)
    total: Annotated[int, Field(ge=0)]
    paid: Annotated[int, Field(ge=0)]
    cancelled: Annotated[int, Field(ge=0)]

class ChannelSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)
    type: Literal['TEST', 'LIVE']
    key: str

class PaymentSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    id: str
    store_id: str = Field(alias='storeId')
    status: Literal['PAID', 'CANCELLED', 'PARTIAL_CANCELLED', 'FAILED', 'READY', 'PENDING', 'PAY_PENDING', 'VIRTUAL_ACCOUNT_ISSUED']
    currency: str
    channel: ChannelSnapshot
    amount: AmountSnapshot

def normalize_payment(payment):
    if isinstance(payment, dict):
        return PaymentSnapshot.model_validate(payment)
    # The injectable lookup also accepts the public SDK's typed payment variants.
    variants = {'PaidPayment': 'PAID', 'CancelledPayment': 'CANCELLED',
                'PartialCancelledPayment': 'PARTIAL_CANCELLED', 'FailedPayment': 'FAILED',
                'ReadyPayment': 'READY', 'PayPendingPayment': 'PAY_PENDING',
                'VirtualAccountIssuedPayment': 'VIRTUAL_ACCOUNT_ISSUED'}
    status = variants.get(type(payment).__name__)
    if status is None:
        raise ValueError('Unsupported payment response.')
    return PaymentSnapshot.model_validate({
        'id': payment.id, 'storeId': payment.store_id, 'status': status,
        'currency': payment.currency, 'channel': {'type': payment.channel.type, 'key': payment.channel.key},
        'amount': {'total': payment.amount.total, 'paid': payment.amount.paid, 'cancelled': payment.amount.cancelled},
    })
