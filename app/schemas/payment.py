"""Strict browser request schemas; payment status is never a client input."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.course import PositiveInt

class CreateOrderInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    course_id: PositiveInt

class ConfirmPaymentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    payment_id: Annotated[str, Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')]
