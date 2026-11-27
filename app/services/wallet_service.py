from contextlib import closing

from app.config import Settings
from app.domain.accounting import build_opening_entries
from app.domain.ledger import chain_entries
from app.domain.rules import validate_amount_minor, validate_currency, validate_uuid
from app.errors import AppError
from app.persistence.database import read_transaction, write_transaction
from app.persistence.repositories.ledger_entry_repository import (
    LedgerEntryRecord,
    get_last_entry_hash,
    insert_ledger_entries,
    list_entries_by_wallet,
)
from app.persistence.repositories.transaction_repository import create_transaction
from app.persistence.repositories.user_repository import get_user_by_id
from app.persistence.repositories.wallet_repository import (
    WalletRecord,
    create_wallet,
    get_system_wallet,
    get_wallet_by_id,
    update_wallet_balance,
)
from app.persistence.schema import SYSTEM_USER_ID
from app.providers import ClockProvider, DatabaseConnectionProvider, IdentifierProvider


class WalletService:
    def __init__(
        self,
        db_provider: DatabaseConnectionProvider,
        clock_provider: ClockProvider,
        id_provider: IdentifierProvider,
        settings: Settings,
    ) -> None:
        self.db_provider = db_provider
        self.clock_provider = clock_provider
        self.id_provider = id_provider
        self.settings = settings

    def create_wallet(
        self,
        user_id: str,
        currency: str,
        opening_balance_minor: int = 0,
    ) -> WalletRecord:
        valid_user_id = validate_uuid(user_id, "user_id")
        if valid_user_id == SYSTEM_USER_ID:
            raise AppError(422, "SYSTEM_USER_FORBIDDEN", "System user cannot own user wallets.")
        valid_currency = validate_currency(currency, self.settings.supported_currencies)
        valid_amount = validate_amount_minor(
            opening_balance_minor,
            allow_zero=True,
            max_amount_minor=self.settings.max_amount_minor,
        )

        wallet_id = self.id_provider.new_id()
        now_iso = self.clock_provider.now_utc().isoformat()

        with closing(self.db_provider.get_connection()) as conn, write_transaction(conn):
            if get_user_by_id(conn, valid_user_id) is None:
                raise AppError(404, "NOT_FOUND", "User not found.")

            wallet = create_wallet(
                conn,
                wallet_id=wallet_id,
                user_id=valid_user_id,
                currency=valid_currency,
                balance_minor=valid_amount,
                created_at=now_iso,
            )

            if valid_amount > 0:
                sys_wallet = get_system_wallet(conn, valid_currency)
                if sys_wallet is None:
                    raise AppError(500, "INTERNAL_ERROR", "System wallet is missing.")

                tx_id = self.id_provider.new_id()
                create_transaction(
                    conn,
                    transaction_id=tx_id,
                    tx_type="opening",
                    amount_minor=valid_amount,
                    currency=valid_currency,
                    created_at=now_iso,
                )
                entries = build_opening_entries(
                    wallet_id=wallet.id,
                    system_wallet_id=sys_wallet.id,
                    amount_minor=valid_amount,
                    currency=valid_currency,
                )
                chained = chain_entries(
                    entries,
                    transaction_id=tx_id,
                    created_at=now_iso,
                    initial_prev_hash=get_last_entry_hash(conn),
                )
                insert_ledger_entries(conn, chained)
                update_wallet_balance(conn, sys_wallet.id, sys_wallet.balance_minor - valid_amount)

            return wallet

    def get_wallet(self, wallet_id: str) -> WalletRecord:
        valid_id = validate_uuid(wallet_id, "wallet_id")
        with closing(self.db_provider.get_connection()) as conn, read_transaction(conn):
            wallet = get_wallet_by_id(conn, valid_id)
            if wallet is None:
                raise AppError(404, "NOT_FOUND", "Wallet not found.")
            return wallet

    def get_wallet_entries(
        self,
        wallet_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LedgerEntryRecord]:
        valid_id = validate_uuid(wallet_id, "wallet_id")
        with closing(self.db_provider.get_connection()) as conn, read_transaction(conn):
            if get_wallet_by_id(conn, valid_id) is None:
                raise AppError(404, "NOT_FOUND", "Wallet not found.")
            return list_entries_by_wallet(conn, valid_id, limit=limit, offset=offset)
