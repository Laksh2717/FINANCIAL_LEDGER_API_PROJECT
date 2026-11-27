from typing import Annotated

from fastapi import APIRouter
from pydantic import AfterValidator, BaseModel, StrictInt, field_validator

from app.domain.rules import validate_amount_minor, validate_idempotency_key, validate_uuid

router = APIRouter(prefix="/transfers", tags=["transfers"])

IdempotencyKey = Annotated[str, AfterValidator(validate_idempotency_key)]


class TransferRequest(BaseModel):
    source_wallet_id: str
    destination_wallet_id: str
    amount_minor: StrictInt
    currency: str

    @field_validator("source_wallet_id")
    @classmethod
    def validate_source_wallet_id(cls, value: str) -> str:
        return validate_uuid(value, "source_wallet_id")

    @field_validator("destination_wallet_id")
    @classmethod
    def validate_destination_wallet_id(cls, value: str) -> str:
        return validate_uuid(value, "destination_wallet_id")

    @field_validator("amount_minor")
    @classmethod
    def validate_amount(cls, value: int) -> int:
        return validate_amount_minor(value)


class TransferEntryResponse(BaseModel):
    seq: int
    transaction_id: str
    wallet_id: str
    direction: str
    amount_minor: int
    currency: str
    created_at: str
    prev_hash: str
    entry_hash: str


class TransferResponse(BaseModel):
    id: str
    source_wallet_id: str
    destination_wallet_id: str
    amount_minor: int
    currency: str
    created_at: str
    entries: list[TransferEntryResponse]
