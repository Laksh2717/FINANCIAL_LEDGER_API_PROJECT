import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.accounting import Direction, EntryDraft

GENESIS_PREV_HASH = "0" * 64


@dataclass(frozen=True)
class ChainedEntry:
    transaction_id: str
    wallet_id: str
    direction: Direction
    amount_minor: int
    currency: str
    created_at: str
    prev_hash: str
    entry_hash: str


def compute_entry_hash(
    prev_hash: str,
    transaction_id: str,
    wallet_id: str,
    direction: Direction | str,
    amount_minor: int,
    currency: str,
    created_at: str,
) -> str:
    payload = json.dumps(
        [prev_hash, transaction_id, wallet_id, direction, amount_minor, currency, created_at],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chain_entries(
    entries: Sequence[EntryDraft],
    transaction_id: str,
    created_at: str,
    initial_prev_hash: str = GENESIS_PREV_HASH,
) -> list[ChainedEntry]:
    chained: list[ChainedEntry] = []
    prev_hash = initial_prev_hash
    for entry in entries:
        entry_hash = compute_entry_hash(
            prev_hash=prev_hash,
            transaction_id=transaction_id,
            wallet_id=entry.wallet_id,
            direction=entry.direction,
            amount_minor=entry.amount_minor,
            currency=entry.currency,
            created_at=created_at,
        )
        chained.append(
            ChainedEntry(
                transaction_id=transaction_id,
                wallet_id=entry.wallet_id,
                direction=entry.direction,
                amount_minor=entry.amount_minor,
                currency=entry.currency,
                created_at=created_at,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )
        )
        prev_hash = entry_hash
    return chained


def compute_request_hash(method: str, path: str, body: Any = None) -> str:
    canonical_body = (
        "" if body is None else json.dumps(body, sort_keys=True, separators=(",", ":"))
    )
    payload = json.dumps(
        [method.upper(), path, canonical_body],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
