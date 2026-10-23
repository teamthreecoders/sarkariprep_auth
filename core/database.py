from typing import Any
from psycopg2 import connect
from psycopg2.errors import ConnectionException, ConnectionDoesNotExist, UniqueViolation

from exceptions.auth import UserAlreadyExistsException
from .config import DBConfig
from .logger import logger


class DBConn:
    """
    PostgreSQL connection wrapper with context manager support.

    Usage:
        with DBConn() as db:
            rows = db.execute_query(query="SELECT ...", variables=(...))
            db.execute_command(query="INSERT ...", variables=(...))
    """

    def __init__(self, autocommit: bool = False):
        self._conn = None
        self._cursor = None
        self.autocommit = autocommit
        self._connect()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        logger.info(f"◉ Connecting...\n⟪{DBConfig.HOST}⟫")
        try:
            conn = connect(
                database=DBConfig.DATABASE,
                user=DBConfig.USER,
                password=DBConfig.PASSWORD,
                host=DBConfig.HOST,
                port=DBConfig.PORT,
                sslmode=DBConfig.SSLMODE,
                connect_timeout=DBConfig.CONNECT_TIMEOUT,
            )
            conn.autocommit = self.autocommit
            self._conn = conn
            self._cursor = self._conn.cursor()
            logger.info(f"✅ Connection established!\n⟪{conn.info}⟫")
        except ConnectionException as error:
            logger.error(f"⛓️‍💥❌ Connection failed!\n⁉️ CAUSE: {error}")
            raise
        except TimeoutError as error:
            logger.error(f"❌ TIMEOUT: Connection failed!\n⁉️ CAUSE: {error}")
            raise
        except Exception as error:
            logger.error(f"⛓️‍💥❌ Cannot connect.\n⁉️ CAUSE: {error}")
            raise

    def reconnect(self) -> None:
        """Close any existing connection and open a fresh one."""
        self.close()
        self._connect()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "DBConn":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False  # do not suppress exceptions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        """Raise if the connection or cursor is not usable."""
        if self._conn is None or self._conn.closed != 0:
            raise ConnectionDoesNotExist("No active DB connection. Call reconnect().")
        if self._cursor is None or self._cursor.closed != 0:
            self._cursor = self._conn.cursor()

    def _log_query(self, query: str) -> None:
        logger.info(
            f"\n{'~~🧿 Execute Query ~~'.center(100, '%')}\n"
            f"Query::\n{query}\n"
            f"{'~~END~~'.center(100, '%')}"
        )

    def _mogrify(self, query: str, variables: Any) -> str:
        return self._cursor.mogrify(query, variables).decode("utf-8")

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    def execute_query(self, *, query: str, variables: Any = None, fetchone:bool = False, limit:int = 200) -> list[tuple] | tuple:
        """
        Run a SELECT and return all rows.
        Raises ValueError if the query is not a SELECT.
        """
        # if query.strip().split()[0].upper() != "SELECT":
        #     raise ValueError("execute_query only accepts SELECT statements.")

        self._require_open()
        debug_sql = self._mogrify(query, variables)
        self._log_query(debug_sql)

        try:
            logger.info("⏳ QUERY SUBMITTED")
            self._cursor.execute(query, variables)
            rows = self._cursor.fetchone() if  fetchone else self._cursor.fetchall()
            logger.info(f"✅ Query complete — {self._cursor.rowcount} row(s) fetched.")
            return rows
        except Exception as err:
            logger.error(f"❌ Query execution FAILED!\nCAUSE: {err}")
            raise

    def execute_command(self, *, query: str, variables: Any = None) -> int:
        """
        Run an INSERT / UPDATE / DELETE and return the number of affected rows.
        Commits automatically; rolls back on error.
        """
        self._require_open()
        debug_sql = self._mogrify(query, variables)
        self._log_query(debug_sql)

        try:
            logger.info("⏳ QUERY SUBMITTED")
            self._cursor.execute(query,variables)
            rows_affected = self._cursor.rowcount
            logger.info(f"{rows_affected} row(s) affected.")
            return rows_affected
        except UniqueViolation as err:
            self.rollback()
            logger.warning(f"⚠️ User is already exist.\nCAUSE: {err}")
            raise UserAlreadyExistsException
        except Exception as err:
            self.rollback()
            logger.error(f"❌ Query execution FAILED (rolled back)!\nCAUSE: {err}")
            raise


    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def commit(self) -> None:
        if self._conn and self._conn.closed == 0:
            self._conn.commit()
            logger.info("COMMIT successful.")
        else:
            raise ConnectionDoesNotExist("Cannot commit — no active connection.")

    def rollback(self):
        if self._conn and self._conn.closed == 0:
            self._conn.rollback()
            logger.info("ROLLBACK successful")
        else:
            raise ConnectionDoesNotExist("Cannot rollback — no active connection.")

    def close(self) -> None:
        if self._cursor and not self._cursor.closed:
            self._cursor.close()
        if self._conn and self._conn.closed == 0:
            self._conn.close()
        logger.info("DB connection closed.")