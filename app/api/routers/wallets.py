from fastapi import APIRouter, Request
from pydantic import BaseModel, StrictInt

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
    return WalletResponse(
        id=wallet.id,
        user_id=wallet.user_id,
        currency=wallet.currency,
        balance_minor=wallet.balance_minor,
        created_at=wallet.created_at,
    )
