import uuid

import pytest

from app.config import MAX_AMOUNT_MINOR
from app.domain.accounting import (
    EntryDraft,
    apply_entries_to_balances,
    assert_balanced_entries,
    build_opening_entries,
    build_reversal_entries,
    build_transfer_entries,
)
from app.domain.rules import (
    WalletState,
    ensure_sufficient_balance,
    validate_amount_minor,
    validate_currency,
    validate_idempotency_key,
    validate_reversal_target,
    validate_transfer,
    validate_uuid,
)
from app.errors import AppError


def test_validate_uuid_accepts_valid_and_rejects_malformed() -> None:
    sample = str(uuid.uuid4())
    assert validate_uuid(sample) == sample
    assert validate_uuid(sample.upper()) == sample

    for bad in ("not-a-uuid", "1234", sample.replace("-", ""), 123):
        with pytest.raises(AppError) as exc:
            validate_uuid(bad, "wallet_id")
        assert exc.value.status_code == 400


def test_validate_currency() -> None:
    assert validate_currency("INR") == "INR"
    assert validate_currency("USD") == "USD"

    with pytest.raises(AppError) as exc_empty:
        validate_currency("")
    assert exc_empty.value.status_code == 400

    with pytest.raises(AppError) as exc_unsupported:
        validate_currency("EUR")
    assert exc_unsupported.value.status_code == 422


def test_validate_amount_minor() -> None:
    assert validate_amount_minor(0, allow_zero=True) == 0
    assert validate_amount_minor(1) == 1
    assert validate_amount_minor(MAX_AMOUNT_MINOR) == MAX_AMOUNT_MINOR

    for bad in (-1, 1.5, "100", True, False, None):
        with pytest.raises(AppError) as exc:
            validate_amount_minor(bad, allow_zero=True)
        assert exc.value.status_code == 400

    with pytest.raises(AppError) as exc_zero:
        validate_amount_minor(0, allow_zero=False)
    assert exc_zero.value.status_code == 400

    with pytest.raises(AppError) as exc_over:
        validate_amount_minor(MAX_AMOUNT_MINOR + 1)
    assert exc_over.value.status_code == 422


def test_validate_idempotency_key() -> None:
    assert validate_idempotency_key("req_123-ABC") == "req_123-ABC"
    assert validate_idempotency_key("a" * 64) == "a" * 64

    for bad in (None, "", "bad key", "bad/key", "a" * 65):
        with pytest.raises(AppError) as exc:
            validate_idempotency_key(bad)
        assert exc.value.status_code == 400


def test_transfer_and_reversal_rules() -> None:
    w1 = WalletState(id="w1", currency="INR", balance_minor=500)
    w2 = WalletState(id="w2", currency="INR", balance_minor=100)
    w_usd = WalletState(id="w3", currency="USD", balance_minor=500)
    w_sys = WalletState(id="wsys", currency="INR", balance_minor=0, is_system=True)

    validate_transfer(w1, w2, 500, "INR")

    with pytest.raises(AppError) as exc_same:
        validate_transfer(w1, w1, 100, "INR")
    assert exc_same.value.status_code == 422

    with pytest.raises(AppError) as exc_sys:
        validate_transfer(w_sys, w2, 100, "INR")
    assert exc_sys.value.status_code == 422

    with pytest.raises(AppError) as exc_curr:
        validate_transfer(w1, w_usd, 100, "INR")
    assert exc_curr.value.status_code == 422

    with pytest.raises(AppError) as exc_funds:
        validate_transfer(w1, w2, 501, "INR")
    assert exc_funds.value.status_code == 422
    assert exc_funds.value.code == "INSUFFICIENT_FUNDS"

    # System wallet is allowed to go negative (e.g. funding openings)
    ensure_sufficient_balance(w_sys, 1000)

    validate_reversal_target("transfer", already_reversed=False)
    with pytest.raises(AppError) as exc_not_transfer:
        validate_reversal_target("opening", already_reversed=False)
    assert exc_not_transfer.value.status_code == 404

    with pytest.raises(AppError) as exc_dup_rev:
        validate_reversal_target("transfer", already_reversed=True)
    assert exc_dup_rev.value.status_code == 409


def test_double_entry_builders_zero_sum_and_integer_precision() -> None:
    balances = {"sys": 0, "alice": 0, "bob": 0}

    opening = build_opening_entries("alice", "sys", 10_000, "INR")
    balances = apply_entries_to_balances(balances, opening)
    assert balances == {"sys": -10_000, "alice": 10_000, "bob": 0}
    assert sum(balances.values()) == 0  # BR-3

    # TQ-6: 1,000 transfers of 1 paisa add up exactly
    for _ in range(1000):
        tx_entries = build_transfer_entries("alice", "bob", 1, "INR")
        balances = apply_entries_to_balances(balances, tx_entries)

    assert balances == {"sys": -10_000, "alice": 9_000, "bob": 1_000}
    assert sum(balances.values()) == 0

    reversal = build_reversal_entries(build_transfer_entries("alice", "bob", 500, "INR"))
    assert reversal == [
        EntryDraft(wallet_id="alice", direction="CREDIT", amount_minor=500, currency="INR"),
        EntryDraft(wallet_id="bob", direction="DEBIT", amount_minor=500, currency="INR"),
    ]


def test_assert_balanced_entries_rejects_invalid_sets() -> None:
    with pytest.raises(ValueError):
        assert_balanced_entries([])

    with pytest.raises(ValueError):
        assert_balanced_entries(
            [
                EntryDraft("a", "DEBIT", 100, "INR"),
                EntryDraft("b", "CREDIT", 99, "INR"),
            ]
        )

    with pytest.raises(ValueError):
        assert_balanced_entries(
            [
                EntryDraft("a", "DEBIT", 100, "INR"),
                EntryDraft("b", "CREDIT", 100, "USD"),
            ]
        )
