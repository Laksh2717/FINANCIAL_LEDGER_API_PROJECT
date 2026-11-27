from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, StrictInt

from app.persistence.repositories.wallet_repository import WalletRecord
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallets", tags=["wallets"])


class CreateWalletRequest(BaseModel):
    user_id: str
    currency: str
    opening_balance_minor: StrictInt = 0


class WalletResponse(BaseModel):
    id: str
    user_id: str
    currency: str
    balance_minor: int
    created_at: str


class LedgerEntryResponse(BaseModel):
    seq: int
    transaction_id: str
    wallet_id: str
    direction: str
    amount_minor: int
    currency: str
    created_at: str
    prev_hash: str
    entry_hash: str


class WalletEntriesResponse(BaseModel):
    wallet_id: str
    limit: int
    offset: int
    entries: list[LedgerEntryResponse]


def _to_wallet_response(wallet: WalletRecord) -> WalletResponse:
    return WalletResponse(
        id=wallet.id,
        user_id=wallet.user_id,
        currency=wallet.currency,
        balance_minor=wallet.balance_minor,
        created_at=wallet.created_at,
    )


def _service(request: Request) -> WalletService:
    return WalletService(
        db_provider=request.app.state.db_provider,
        clock_provider=request.app.state.clock_provider,
        id_provider=request.app.state.id_provider,
        settings=request.app.state.settings,
    )


@router.post("", response_model=WalletResponse, status_code=201)
def create_wallet_endpoint(payload: CreateWalletRequest, request: Request) -> WalletResponse:
    wallet = _service(request).create_wallet(
        user_id=payload.user_id,
        currency=payload.currency,
        opening_balance_minor=payload.opening_balance_minor,
    )
    return _to_wallet_response(wallet)


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet_endpoint(wallet_id: str, request: Request) -> WalletResponse:
    wallet = _service(request).get_wallet(wallet_id)
    return _to_wallet_response(wallet)


@router.get("/{wallet_id}/entries", response_model=WalletEntriesResponse)
def get_wallet_entries_endpoint(
    wallet_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WalletEntriesResponse:
    entries = _service(request).get_wallet_entries(wallet_id, limit=limit, offset=offset)
    return WalletEntriesResponse(
        wallet_id=wallet_id,
        limit=limit,
        offset=offset,
        entries=[
            LedgerEntryResponse(
                seq=e.seq,
                transaction_id=e.transaction_id,
                wallet_id=e.wallet_id,
                direction=e.direction,
                amount_minor=e.amount_minor,
                currency=e.currency,
                created_at=e.created_at,
                prev_hash=e.prev_hash,
                entry_hash=e.entry_hash,
            )
            for e in entries
        ],
    )
