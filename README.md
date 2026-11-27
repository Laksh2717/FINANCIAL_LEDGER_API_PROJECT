# Financial Ledger & Digital Wallet API

Backend REST API built with Python 3.12+, FastAPI, and SQLite.

## Project Structure

- `app/api/` - HTTP layer (routers and request/response schemas)
- `app/services/` - Application service layer
- `app/domain/` - Financial rules and double-entry ledger logic
- `app/persistence/` - SQLite database access and repositories
- `tests/` - Automated tests

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```
