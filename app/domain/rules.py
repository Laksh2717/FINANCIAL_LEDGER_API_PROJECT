import re
import uuid
from dataclasses import dataclass

from app.config import MAX_AMOUNT_MINOR, SUPPORTED_CURRENCIES
from app.errors import AppError

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class WalletState:
    id: str
    currency: str
    balance_minor: int
    is_system: bool = False


def validate_uuid(value: object, field_name: str = "id") -> str:
    if not isinstance(value, str):
        raise AppError(400, "BAD_REQUEST", f"Invalid UUID for {field_name}.")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise AppError(400, "BAD_REQUEST", f"Invalid UUID for {field_name}.") from exc
    if str(parsed) != value.lower():
        raise AppError(400, "BAD_REQUEST", f"Invalid UUID for {field_name}.")
    return str(parsed)


def validate_currency(
    currency: object,
    supported_currencies: tuple[str, ...] = SUPPORTED_CURRENCIES,
) -> str:
    if not isinstance(currency, str) or not currency:
        raise AppError(400, "BAD_REQUEST", "Currency must be a non-empty string.")
    if currency not in supported_currencies:
        raise AppError(422, "UNSUPPORTED_CURRENCY", f"Unsupported currency: {currency}.")
    return currency


def validate_amount_minor(
    amount: object,
    *,
    allow_zero: bool = False,
    max_amount_minor: int = MAX_AMOUNT_MINOR,
) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise AppError(400, "BAD_REQUEST", "Amount must be an integer in minor units.")
    if amount < 0:
        raise AppError(400, "BAD_REQUEST", "Amount must not be negative.")
    if not allow_zero and amount == 0:
        raise AppError(400, "BAD_REQUEST", "Amount must be greater than zero.")
    if amount > max_amount_minor:
        raise AppError(
            422,
            "AMOUNT_LIMIT_EXCEEDED",
            f"Amount exceeds maximum of {max_amount_minor} minor units.",
        )
    return amount


def validate_idempotency_key(key: str | None) -> str:
    if key is None or not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise AppError(
            400,
            "BAD_REQUEST",
            "Idempotency-Key header must be 1 to 64 characters (letters, digits, '-', '_').",
        )
    return key


def ensure_sufficient_balance(wallet: WalletState, amount_minor: int) -> None:
    if not wallet.is_system and wallet.balance_minor < amount_minor:
        raise AppError(422, "INSUFFICIENT_FUNDS", "Insufficient funds in wallet.")


def validate_transfer(
    source: WalletState,
    destination: WalletState,
    amount_minor: int,
    currency: str,
) -> None:
    if source.id == destination.id:
        raise AppError(422, "SAME_WALLET", "Source and destination wallets must differ.")
    if source.is_system or destination.is_system:
        raise AppError(422, "SYSTEM_WALLET_FORBIDDEN", "System wallets cannot be used directly.")
    if source.currency != currency or destination.currency != currency:
        raise AppError(422, "CURRENCY_MISMATCH", "Wallets must match the transfer currency.")
    ensure_sufficient_balance(source, amount_minor)


def validate_reversal_target(tx_type: str, already_reversed: bool) -> None:
    if tx_type != "transfer":
        raise AppError(404, "NOT_FOUND", "Transfer not found.")
    if already_reversed:
        raise AppError(409, "CONFLICT", "Transfer has already been reversed.")
