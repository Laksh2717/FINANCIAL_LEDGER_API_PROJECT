# ADR-002: Architecture Style Decision

## Status
Accepted

## Date
24 November 2026

## Context

The Financial Ledger & Digital Wallet API requires a clear separation of API handling, business logic, domain rules and database operations.

The architecture must support the requirements specified in SRS v1.0 while keeping the system simple to develop, test and maintain.

## Decision

A layered monolithic architecture is selected.

The application is organized into four layers:

1. **API Layer:** Handles HTTP requests, responses and validation.
2. **Service Layer:** Implements application operations such as wallet creation, transfers, reversals and reconciliation.
3. **Domain Layer:** Contains financial rules, balance calculations and ledger logic.
4. **Persistence Layer:** Handles SQLite database connections, queries and transactions.

All layers operate within a single deployable FastAPI application.

## Alternatives Considered

### Option 1: Layered Monolithic Architecture
- Separates responsibilities into distinct layers.
- Keeps the application as a single deployable service.
- Simplifies database transaction management.

### Option 2: Microservices Architecture
- Separates functionality into independently deployed services.
- Introduces additional communication and deployment complexity.
- Makes atomic financial transactions across components more difficult.

### Option 3: Single-Layer Architecture
- Places API handling, business logic and database operations together.
- Is simpler initially but makes testing and maintenance harder.

## Reason for Selection

The layered monolithic architecture provides separation of responsibilities without introducing unnecessary deployment complexity.

It also allows financial operations and their corresponding database updates to remain within a single SQLite transaction.

## Consequences

### Positive Consequences
- Clear separation of responsibilities.
- Easier testing and maintenance.
- Supports atomic financial transactions.
- Simple deployment as one application.

### Negative Consequences
- Layers must be maintained consistently.
- The application is deployed as a single unit.

## References

- [[SQLite-Transactions]]
- [[Double-Entry-Bookkeeping]]
- [[Database-Concurrency-and-Race-Conditions]]

## Related Requirements

- FR-1: Wallet Initialization
- FR-2: Idempotent Transfers
- FR-3: Concurrency
- FR-4: Audit Trail and Reversal
- FR-5: Reconciliation
