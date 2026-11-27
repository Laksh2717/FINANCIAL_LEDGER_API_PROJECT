# Database Design – Financial Ledger & Digital Wallet API

## 1. Scope

This document describes the SQLite database design required by SRS v1.0. It is a design document only.

The database contains the five entities specified in SRS Section 6.1: `users`, `wallets`, `ledger_transactions`, `ledger_entries` and `idempotency_keys`. No additional product features or tables are introduced.

## 2. Tables

### 2.1 `users`

| Column | Purpose | Constraint |
|---|---|---|
| `id` | User identifier | Primary key; generated UUID |
| `name` | User name | Required for a normal user |
| `email` | User email | Unique for normal users |
| `created_at` | Creation timestamp | UTC |

One reserved row represents the system user. The system user owns the internal system wallets.

### 2.2 `wallets`

| Column | Purpose | Constraint |
|---|---|---|
| `id` | Wallet identifier | Primary key |
| `user_id` | Owner | Foreign key to `users.id` |
| `currency` | Wallet currency | Supported currency; part of unique pair |
| `balance_minor` | Stored balance in minor units | Integer; user-wallet balance cannot be negative |
| `is_system` | Identifies a system wallet | Boolean-style value |
| `created_at` | Creation timestamp | UTC |

Required uniqueness: `(user_id, currency)`. System wallets belong to the reserved system user, with one internal wallet per supported currency.

### 2.3 `ledger_transactions`

| Column | Purpose | Constraint |
|---|---|---|
| `id` | Transaction identifier | Primary key |
| `type` | `opening`, `transfer` or `reversal` | Required |
| `amount_minor` | Transaction amount in minor units | Positive integer |
| `currency` | Transaction currency | Required |
| `reverses_transaction_id` | Original transaction for a reversal | Nullable; unique when present; references `ledger_transactions.id` |
| `created_at` | Creation timestamp | UTC |

A reversal is a new transaction linked to the original transfer. The unique reversal reference prevents a transfer from being reversed more than once.

### 2.4 `ledger_entries`

| Column | Purpose | Constraint |
|---|---|---|
| `seq` | Ledger sequence | Primary key; increasing |
| `transaction_id` | Parent transaction | Foreign key to `ledger_transactions.id` |
| `wallet_id` | Affected wallet | Foreign key to `wallets.id` |
| `direction` | `DEBIT` or `CREDIT` | Required |
| `amount_minor` | Entry amount in minor units | Positive integer |
| `currency` | Entry currency | Required |
| `created_at` | Entry timestamp | UTC |
| `prev_hash` | Previous entry hash | Required |
| `entry_hash` | Hash of this entry and previous hash | Required |

Every transaction has balanced debit and credit entries. Ledger entries are append-only.

### 2.5 `idempotency_keys`

| Column | Purpose | Constraint |
|---|---|---|
| `key` | Client idempotency key | Primary key |
| `request_hash` | SHA-256 request fingerprint | Required |
| `response_status` | Original HTTP response status | Required |
| `response_body` | Original response body | Required |
| `created_at` | Creation timestamp | UTC |

The key and response are stored atomically with a successful transfer or reversal. A repeated key with the same fingerprint replays the stored response; a different fingerprint is rejected.

## 3. Relationships

- One user can own multiple wallets; each wallet belongs to one user.
- One ledger transaction has multiple ledger entries.
- Each ledger entry belongs to one transaction and affects one wallet.
- A ledger transaction may reference the original transaction it reverses.
- `reverses_transaction_id` is unique, allowing at most one reversal per original transaction.
- Idempotency keys store request and response information. The SRS does not specify a separate foreign-key relationship for this table.

## 4. Integrity Rules

1. Debits equal credits in every ledger transaction.
2. A wallet balance equals its credits minus its debits.
3. For each currency, all wallet balances including the system wallet sum to zero.
4. Ledger entries and ledger transactions cannot be updated or deleted through normal database access.
5. A user wallet cannot have a negative balance; only a system wallet may be negative.
6. Each ledger entry hash includes the previous entry hash and the specified entry fields.
7. Wallet creation and any opening entries are saved in one database transaction.
8. A successful transfer writes its debit, credit, balance updates and idempotency response in one transaction.
9. A reversal creates new entries with debit and credit swapped; original ledger records remain unchanged.

## 5. Constraints and Triggers

The design shall enforce primary keys, foreign keys, unique user email, unique `(user_id, currency)`, unique `reverses_transaction_id`, positive entry amounts and valid debit/credit directions. Triggers reject UPDATE and DELETE on `ledger_entries` and `ledger_transactions`.

SQLite foreign-key enforcement must be enabled for database connections.

## 6. Indexes

Primary-key and unique constraints provide indexes for their corresponding lookups. Additional indexes should be added only when justified by actual query patterns. The SRS does not prescribe a fixed list of additional indexes.

## 7. Source

SRS v1.0, Section 6.1, FR-1 to FR-5 and BR-1 to BR-6.
