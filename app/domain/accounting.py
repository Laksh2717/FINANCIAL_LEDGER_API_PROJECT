from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Direction = Literal["DEBIT", "CREDIT"]


@dataclass(frozen=True)
class EntryDraft:
    wallet_id: str
    direction: Direction
    amount_minor: int
    currency: str


def assert_balanced_entries(entries: Sequence[EntryDraft]) -> None:
    if not entries:
        raise ValueError("Transaction must contain at least one ledger entry.")

    currencies = {entry.currency for entry in entries}
    if len(currencies) != 1:
        raise ValueError("All entries in a transaction must share one currency.")

    total_debits = 0
    total_credits = 0
    for entry in entries:
        if entry.amount_minor <= 0:
            raise ValueError("Ledger entry amount_minor must be positive.")
        if entry.direction == "DEBIT":
            total_debits += entry.amount_minor
        elif entry.direction == "CREDIT":
            total_credits += entry.amount_minor
        else:
            raise ValueError(f"Invalid direction: {entry.direction}")

    if total_debits != total_credits:
        raise ValueError(f"Unbalanced transaction: debits={total_debits}, credits={total_credits}")


def build_opening_entries(
    wallet_id: str,
    system_wallet_id: str,
    amount_minor: int,
    currency: str,
) -> tuple[EntryDraft, EntryDraft]:
    entries = (
        EntryDraft(
            wallet_id=system_wallet_id,
            direction="DEBIT",
            amount_minor=amount_minor,
            currency=currency,
        ),
        EntryDraft(
            wallet_id=wallet_id,
            direction="CREDIT",
            amount_minor=amount_minor,
            currency=currency,
        ),
    )
    assert_balanced_entries(entries)
    return entries


def build_transfer_entries(
    source_wallet_id: str,
    destination_wallet_id: str,
    amount_minor: int,
    currency: str,
) -> tuple[EntryDraft, EntryDraft]:
    entries = (
        EntryDraft(
            wallet_id=source_wallet_id,
            direction="DEBIT",
            amount_minor=amount_minor,
            currency=currency,
        ),
        EntryDraft(
            wallet_id=destination_wallet_id,
            direction="CREDIT",
            amount_minor=amount_minor,
            currency=currency,
        ),
    )
    assert_balanced_entries(entries)
    return entries


def build_reversal_entries(original_entries: Sequence[EntryDraft]) -> list[EntryDraft]:
    reversed_entries = [
        EntryDraft(
            wallet_id=entry.wallet_id,
            direction="CREDIT" if entry.direction == "DEBIT" else "DEBIT",
            amount_minor=entry.amount_minor,
            currency=entry.currency,
        )
        for entry in original_entries
    ]
    assert_balanced_entries(reversed_entries)
    return reversed_entries


def apply_entries_to_balances(
    balances: dict[str, int],
    entries: Sequence[EntryDraft],
) -> dict[str, int]:
    assert_balanced_entries(entries)
    updated = dict(balances)
    for entry in entries:
        delta = entry.amount_minor if entry.direction == "CREDIT" else -entry.amount_minor
        updated[entry.wallet_id] = updated.get(entry.wallet_id, 0) + delta
    return updated
