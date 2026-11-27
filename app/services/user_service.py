from contextlib import closing

from app.persistence.database import write_transaction
from app.persistence.repositories.user_repository import UserRecord, create_user
from app.providers import ClockProvider, DatabaseConnectionProvider, IdentifierProvider


class UserService:
    def __init__(
        self,
        db_provider: DatabaseConnectionProvider,
        clock_provider: ClockProvider,
        id_provider: IdentifierProvider,
    ) -> None:
        self.db_provider = db_provider
        self.clock_provider = clock_provider
        self.id_provider = id_provider

    def create_user(self, name: str, email: str) -> UserRecord:
        user_id = self.id_provider.new_id()
        created_at = self.clock_provider.now_utc().isoformat()
        with closing(self.db_provider.get_connection()) as conn, write_transaction(conn):
            return create_user(conn, user_id, name, email, created_at)
