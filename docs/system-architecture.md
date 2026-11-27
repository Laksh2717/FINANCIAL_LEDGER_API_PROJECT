# System Architecture – Financial Ledger & Digital Wallet API

## 1. Overview

The Financial Ledger & Digital Wallet API is a REST-based backend application that manages users, wallets and financial transactions using double-entry accounting.

The system uses FastAPI and SQLite and is designed as a single deployable application.

## 2. Architecture Style

The system follows a layered architecture:

1. API Layer
2. Service Layer
3. Domain Layer
4. Persistence Layer

Each layer has a separate responsibility.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3.12+ |
| API Framework | FastAPI |
| Server | Uvicorn |
| Database | SQLite |
| Database Access | sqlite3 |
| Validation | Pydantic |
| Hashing | hashlib (SHA-256) |
| Testing | pytest |
| API Documentation | OpenAPI / Swagger |

The technology selection is documented in [[ADR-001-technology-stack]].

## 4. System Layers

### 4.1 API Layer

- Handles HTTP requests and responses.
- Validates request data using Pydantic.
- Handles required headers and authentication.
- Calls the appropriate service.
- Returns the required HTTP status codes.

### 4.2 Service Layer

- Coordinates user and wallet creation.
- Handles transfers and reversals.
- Manages idempotency.
- Coordinates reconciliation.

### 4.3 Domain Layer

- Enforces double-entry accounting.
- Validates wallet balances and transfer rules.
- Handles reversal rules.
- Calculates and verifies ledger hashes.

All monetary values use integer minor units.

### 4.4 Persistence Layer

- Manages SQLite database connections.
- Executes parameterized SQL queries.
- Stores users, wallets, transactions and ledger entries.
- Manages database transactions.
- Enforces database constraints and integrity rules.

### 4.5 Provider Interfaces

The system uses three provider interfaces as required by the SRS:

- Clock Provider: Supplies the current time.
- Identifier Provider: Generates application identifiers.
- Database Connection Provider: Supplies database connections.

These interfaces allow tests to use substitute implementations.

## 5. Main Components

| Component | Responsibility |
|---|---|
| User API | User creation |
| Wallet API | Wallet creation and balance retrieval |
| Transfer API | Transfer creation and retrieval |
| Reversal API | Transfer reversal |
| Reconciliation API | Ledger reconciliation |
| Health API | Application health check |
| User Service | User operations |
| Wallet Service | Wallet operations |
| Transfer Service | Transfer and idempotency operations |
| Reversal Service | Reversal operations |
| Reconciliation Service | Reconciliation operations |
| Database Access | SQLite operations |

## 6. Database Architecture

The application uses one SQLite database containing:

- `users`
- `wallets`
- `ledger_transactions`
- `ledger_entries`
- `idempotency_keys`

A reserved system user and system wallets are also maintained as required by the SRS.

Foreign keys, constraints and triggers enforce data integrity and ledger immutability.

The detailed schema is documented in the database design document.

## 7. Main Request Flows

### 7.1 Wallet Creation

1. The client sends a wallet creation request.
2. The API validates the request.
3. The Wallet Service coordinates the operation.
4. A database transaction is started.
5. The wallet and any required opening ledger entries are created.
6. The transaction is committed.

### 7.2 Money Transfer

1. The client sends a transfer request with an Idempotency-Key.
2. The API validates the request.
3. A write transaction starts using `BEGIN IMMEDIATE`.
4. The idempotency key is checked.
5. The wallets, currency and available balance are validated.
6. Debit and credit ledger entries are created.
7. Wallet balances and the idempotency response are stored.
8. The transaction is committed.

If the operation fails, the transaction is rolled back.

### 7.3 Transfer Reversal

1. The client requests a reversal with an Idempotency-Key.
2. A write transaction starts using `BEGIN IMMEDIATE`.
3. The idempotency key and original transfer are checked.
4. Reversal conditions and available balance are validated.
5. A new transaction is created with the debit and credit entries reversed.
6. Wallet balances and the idempotency response are stored.
7. The transaction is committed.

The original ledger records remain unchanged.

### 7.4 Reconciliation

1. The administrator sends a request with the admin token.
2. The token is validated.
3. The system checks debit and credit totals.
4. Wallet balances are compared with ledger balances.
5. The ledger hash chain is verified.
6. The reconciliation report is returned.

Reconciliation does not modify database records.

## 8. Transaction and Concurrency Management

- SQLite uses WAL mode.
- Busy timeout is set to 5000 milliseconds.
- Data-changing requests use `BEGIN IMMEDIATE`.
- Balance checks and updates happen in the same transaction.
- Each request uses its own database connection.
- Database busy timeout results in HTTP 503 with `Retry-After` and no writes.

Idempotency checks and record creation happen within the same transaction as the associated financial operation.

## 9. Deployment

The application runs as a single FastAPI service using Uvicorn and one SQLite database file.

No external payment gateway or distributed database is required.

## 10. Related Documents

- [[ADR-001-technology-stack]]
- [[SQLite-Transactions]]
- [[SQLite-Begin-Immediate-and-Locking]]
- [[SQLite-WAL-Mode]]
- `docs/architecture/component-design.md`
- `docs/diagrams/er-diagram.mmd`

## 11. Related Requirements

- FR-1: Wallet Initialization
- FR-2: Idempotent Transfers
- FR-3: Concurrency
- FR-4: Immutable Audit Trail and Reversals
- FR-5: Ledger Reconciliation
