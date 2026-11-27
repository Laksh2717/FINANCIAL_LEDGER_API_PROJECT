
# ADR-001: Technology Stack Decision

## Status
Accepted

## Date
19 November 2026

## Context

The Financial Ledger & Digital Wallet API requires a REST API with reliable financial transactions, concurrency control, idempotency, an immutable ledger and reconciliation.

The technology stack must support the requirements specified in the submitted SRS v1.0.

## Decision

The following technology stack is selected:

| Component | Technology |
|---|---|
| Programming Language | Python 3.12+ |
| API Framework | FastAPI |
| ASGI Server | Uvicorn |
| Database | SQLite |
| Database Access | Python built-in sqlite3 |
| Data Validation | Pydantic |
| Hashing | hashlib (SHA-256) |
| Testing | pytest |
| API Testing | Postman |
| API Documentation | OpenAPI / Swagger |
| Version Control | Git and GitHub |
| CI | GitHub Actions |

## Alternatives Considered

### Option 1: Python with FastAPI

- Supports REST API development.
- Provides request validation through Pydantic.
- Supports automatic OpenAPI documentation.
- Python's built-in sqlite3 provides direct control over SQL queries and transactions.
- Supports SHA-256 through hashlib.
- pytest provides automated testing.

### Option 2: Java with Spring Boot

- Provides a structured framework for REST API development.
- Supports database integration and transaction management.
- Provides validation and testing libraries.
- Requires additional framework configuration and abstraction for this project.

## Reason for Selection

Python with FastAPI is selected because it provides a simple development environment while meeting the project's requirements.

Using the built-in sqlite3 module provides direct control over:

- BEGIN IMMEDIATE transactions.
- SQLite WAL mode.
- Busy timeout configuration.
- Database triggers.
- Atomic ledger and balance updates.

This approach makes the database operations easier to understand and verify against the SRS.

## Consequences

### Positive Consequences

- Simple and understandable implementation.
- Direct control over SQLite transactions.
- Built-in support for SHA-256 hashing.
- Automatic API documentation through OpenAPI.
- pytest supports automated testing.
- Suitable for the scope of this project.

### Negative Consequences

- Database transaction management must be handled carefully in application code.
- SQL queries and database operations require explicit implementation.
- SQLite supports only one active writer at a time.
- The application must handle database locking and busy errors.

## References

- [[SQLite-Transactions]]
- [[SQLite-WAL-Mode]]
- [[SQLite-Begin-Immediate-and-Locking]]
- [[SHA-256-Hashing]]
- [[Database-Concurrency-and-Race-Conditions]]

## Related Requirements

- FR-1: Wallet Initialization
- FR-2: Idempotent Transfers
- FR-3: Concurrency
- FR-4: Audit Trail and Reversal
- FR-5: Reconciliation
- TBD-01: Technology Stack
