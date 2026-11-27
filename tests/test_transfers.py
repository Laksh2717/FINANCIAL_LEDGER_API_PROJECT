import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from app.api.routers.transfers import IdempotencyKey, TransferRequest
from app.config import MAX_AMOUNT_MINOR
from app.errors import AppError


def _transfer_payload() -> dict[str, object]:
    return {
        "source_wallet_id": str(uuid.uuid4()),
        "destination_wallet_id": str(uuid.uuid4()),
        "amount_minor": 125,
        "currency": "INR",
    }


def test_transfer_request_accepts_valid_payload() -> None:
    payload = _transfer_payload()

    request = TransferRequest.model_validate(payload)

    assert request.amount_minor == 125
    assert request.currency == "INR"


def test_transfer_request_rejects_missing_fields_and_malformed_wallet_ids() -> None:
    with pytest.raises(ValidationError):
        TransferRequest.model_validate({})

    for field in ("source_wallet_id", "destination_wallet_id"):
        payload = _transfer_payload()
        payload[field] = "not-a-uuid"
        with pytest.raises(AppError) as exc:
            TransferRequest.model_validate(payload)
        assert exc.value.status_code == 400


def test_transfer_request_rejects_non_integer_or_invalid_amounts() -> None:
    for amount in (True, 1.5, "100"):
        payload = _transfer_payload()
        payload["amount_minor"] = amount
        with pytest.raises(ValidationError):
            TransferRequest.model_validate(payload)

    for amount in (0, -1):
        payload = _transfer_payload()
        payload["amount_minor"] = amount
        with pytest.raises(AppError) as exc:
            TransferRequest.model_validate(payload)
        assert exc.value.status_code == 400

    payload = _transfer_payload()
    payload["amount_minor"] = MAX_AMOUNT_MINOR + 1
    with pytest.raises(AppError) as exc:
        TransferRequest.model_validate(payload)
    assert exc.value.status_code == 422


def test_idempotency_key_contract() -> None:
    key_adapter = TypeAdapter(IdempotencyKey)
    assert key_adapter.validate_python("req_123-ABC") == "req_123-ABC"
    assert key_adapter.validate_python("a" * 64) == "a" * 64

    for key in ("", "bad key", "bad/key", "a" * 65):
        with pytest.raises(AppError) as exc:
            key_adapter.validate_python(key)
        assert exc.value.status_code == 400
