from app.domain.accounting import build_transfer_entries
from app.domain.ledger import (
    GENESIS_PREV_HASH,
    chain_entries,
    compute_entry_hash,
    compute_request_hash,
)

NOW = "2026-11-27T14:30:00+00:00"


def test_chain_entries_links_hashes_sequentially() -> None:
    entries = build_transfer_entries("w1", "w2", 500, "INR")
    chained = chain_entries(entries, transaction_id="tx1", created_at=NOW)

    assert len(chained) == 2
    assert chained[0].prev_hash == GENESIS_PREV_HASH
    assert chained[1].prev_hash == chained[0].entry_hash
    assert len(chained[0].entry_hash) == 64
    assert len(chained[1].entry_hash) == 64
    assert chained[0].entry_hash != chained[1].entry_hash

    recomputed_first = compute_entry_hash(
        prev_hash=GENESIS_PREV_HASH,
        transaction_id="tx1",
        wallet_id="w1",
        direction="DEBIT",
        amount_minor=500,
        currency="INR",
        created_at=NOW,
    )
    assert chained[0].entry_hash == recomputed_first


def test_chain_entries_continues_from_last_hash_and_detects_tampering() -> None:
    tx1_entries = chain_entries(
        build_transfer_entries("w1", "w2", 100, "INR"),
        transaction_id="tx1",
        created_at=NOW,
    )
    tx2_entries = chain_entries(
        build_transfer_entries("w2", "w1", 50, "INR"),
        transaction_id="tx2",
        created_at=NOW,
        initial_prev_hash=tx1_entries[-1].entry_hash,
    )

    assert tx2_entries[0].prev_hash == tx1_entries[-1].entry_hash

    tampered_hash = compute_entry_hash(
        prev_hash=tx1_entries[0].prev_hash,
        transaction_id="tx1",
        wallet_id="w1",
        direction="DEBIT",
        amount_minor=101,
        currency="INR",
        created_at=NOW,
    )
    assert tampered_hash != tx1_entries[0].entry_hash


def test_compute_request_hash_is_canonical_and_endpoint_sensitive() -> None:
    h1 = compute_request_hash(
        "post",
        "/v1/transfers",
        {"source_wallet_id": "a", "destination_wallet_id": "b", "amount_minor": 100},
    )
    h2 = compute_request_hash(
        "POST",
        "/v1/transfers",
        {"amount_minor": 100, "destination_wallet_id": "b", "source_wallet_id": "a"},
    )
    assert h1 == h2
    assert len(h1) == 64

    h_diff_path = compute_request_hash(
        "POST",
        "/v1/transfers/123/reversal",
        {"source_wallet_id": "a", "destination_wallet_id": "b", "amount_minor": 100},
    )
    h_diff_method = compute_request_hash(
        "PUT",
        "/v1/transfers",
        {"source_wallet_id": "a", "destination_wallet_id": "b", "amount_minor": 100},
    )
    h_diff_body = compute_request_hash(
        "POST",
        "/v1/transfers",
        {"source_wallet_id": "a", "destination_wallet_id": "b", "amount_minor": 200},
    )
    h_none_body = compute_request_hash("POST", "/v1/transfers/123/reversal")

    assert h_diff_path != h1
    assert h_diff_method != h1
    assert h_diff_body != h1
    assert h_none_body != h_diff_path
