# Component Design – Financial Ledger & Digital Wallet API

## 1. Overview

This document describes the main components of the Financial Ledger & Digital Wallet API and their responsibilities.

The application is divided into four layers: API, Service, Domain and Persistence.

## 2. API Layer

The API layer handles client requests and responses.

| Component | Responsibility | Endpoint |
|---|---|---|
| User API | User creation | POST /v1/users |
| Wallet API | Wallet creation and balance retrieval | POST /v1/wallets, GET /v1/wallets/{id} |
| Wallet API | Ledger entry retrieval | GET /v1/wallets/{id}/entries |
| Transfer API | Transfer creation and retrieval | POST /v1/transfers, GET /v1/transfers/{id} |
| Reversal API | Transfer reversal | POST /v1/transfers/{id}/reversal |
| Reconciliation API | Administrative reconciliation | GET /v1/admin/reconciliation |
| Health API | Health check | GET /health |

The API layer validates requests, extracts required headers and calls the appropriate service.

## 3. Service Layer

The service layer coordinates application operations.

| Component | Responsibility |
|---|---|
| User Service | Creates users |
| Wallet Service | Creates wallets and retrieves balances and entries |
| Transfer Service | Processes transfers and handles idempotency |
| Reversal Service | Processes transfer reversals |
| Reconciliation Service | Coordinates reconciliation checks |

## 4. Domain Layer

The domain layer contains the financial rules.

| Component | Responsibility |
|---|---|
| Accounting Logic | Enforces double-entry accounting |
| Balance Rules | Ensures wallet balance constraints |
| Transfer Rules | Validates transfer conditions |
| Reversal Rules | Validates reversal conditions |
| Ledger Logic | Prepares ledger entries and calculates hashes |
| Reconciliation Logic | Verifies accounting totals, balances and hash chain |

All monetary calculations use integer minor units.

## 5. Persistence Layer

The persistence layer handles database operations using Python's built-in sqlite3 module.

| Component | Responsibility |
|---|---|
| User Repository | User database operations |
| Wallet Repository | Wallet database operations |
| Transaction Repository | Transaction database operations |
| Ledger Entry Repository | Ledger entry database operations |
| Idempotency Repository | Idempotency record operations |
| Database Connection Manager | Provides database connections |
| Transaction Manager | Manages database transactions |

All SQL queries use parameterized statements.

## 6. Provider Interfaces

The system uses the following provider interfaces:

| Interface | Responsibility |
|---|---|
| Clock Provider | Supplies the current time |
| Identifier Provider | Generates identifiers |
| Database Connection Provider | Supplies database connections |

These interfaces allow tests to substitute controlled implementations.

## 7. Main Component Interactions

### 7.1 User and Wallet Creation

1. The API receives and validates the request.
2. The corresponding service coordinates the operation.
3. The Transaction Manager starts a database transaction for data-changing operations.
4. The repository stores the required records.
5. The transaction is committed or rolled back.

### 7.2 Transfer Processing

1. Transfer API receives the request and Idempotency-Key.
2. Transfer Service starts the operation.
3. Transaction Manager starts a write transaction using `BEGIN IMMEDIATE`.
4. Idempotency Repository checks the key and request fingerprint.
5. Transfer Rules and Balance Rules validate the transfer.
6. Accounting Logic prepares the debit and credit entries.
7. Ledger Logic prepares the ledger entries and hashes.
8. Repositories store the entries, update wallet balances and store the idempotency response.
9. The transaction is committed or rolled back.

If the same key and request are received again, the original response is returned without creating another transfer. Reusing a key with a different request fingerprint is rejected with HTTP 422 Unprocessable Entity.

### 7.3 Transfer Reversal

1. Reversal API receives the request.
2. Reversal Service starts the operation.
3. Transaction Manager starts a write transaction using `BEGIN IMMEDIATE`.
4. Idempotency Repository checks the key and request fingerprint.
5. Reversal Rules check whether the original transfer can be reversed and whether it has already been reversed.
6. Balance Rules verify sufficient funds.
7. Accounting Logic prepares the reversed debit and credit entries.
8. Ledger Logic prepares the new reversal entries and hashes.
9. Repositories store the reversal transaction, ledger entries, updated wallet balances and idempotency response.
10. The transaction is committed or rolled back.

If the same key and request are received again, the original response is returned without creating another reversal. Reusing a key with a different request fingerprint is rejected with HTTP 422 Unprocessable Entity.

The original ledger records are not modified.

### 7.4 Reconciliation

1. Reconciliation API receives the administrator request.
2. The admin token is validated.
3. Reconciliation Service coordinates the checks.
4. Repositories retrieve the required records.
5. Reconciliation Logic verifies debit and credit totals, wallet balances and the hash chain.
6. The report is returned.

Reconciliation is read-only.

## 8. Transaction Management

- Each request uses its own database connection.
- Data-changing requests use `BEGIN IMMEDIATE`.
- Balance checks and updates occur in the same transaction.
- Idempotency checks and record creation occur in the same transaction as the financial operation.
- Successful operations are committed.
- Failed operations are rolled back.
- WAL mode and a 5000-millisecond busy timeout are configured.
- A database busy timeout results in HTTP 503 with `Retry-After`.
- Reconciliation checks execute within a single read transaction to ensure a consistent database snapshot.

## 9. Related Documents

- `docs/architecture/system-architecture.md`
- `docs/diagrams/er-diagram.mmd`
- [[ADR-001-technology-stack]]
- [[ADR-002-architecture-style]]
- [[SQLite-Transactions]]
- [[SQLite-Begin-Immediate-and-Locking]]
- [[Database-Concurrency-and-Race-Conditions]]

## 10. Related Requirements

- FR-1: Wallet Initialization
- FR-2: Idempotent Transfers
- FR-3: Concurrency
- FR-4: Immutable Audit Trail and Reversals
- FR-5: Ledger Reconciliation
