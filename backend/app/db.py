"""
PostgreSQL access: a connection pool plus a small migration runner.

Connection pool: opening a Postgres connection costs a TCP + auth round trip
(and often TLS). The pool keeps a few connections open and lends one to each
request. `with get_conn() as conn:` commits on success, rolls back on error,
and returns the connection to the pool.

Migrations: numbered .sql files in backend/migrations run in order, and each
one is recorded in `schema_migrations`. A Postgres *advisory lock* ensures that
when several app instances boot at once (e.g. a deploy with 2 replicas), only
one of them runs the migrations and the others wait.
"""

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_LOCK_ID = 7_236_001  # arbitrary app-wide constant for pg_advisory_lock

_pool: ConnectionPool | None = None


def init_pool(database_url: str, min_size: int = 1, max_size: int = 10) -> ConnectionPool:
    global _pool
    if _pool is not None:
        _pool.close()
    _pool = ConnectionPool(
        database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row},
        # Detect connections the server (or a proxy) silently dropped.
        check=ConnectionPool.check_connection,
        open=True,
    )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("database pool not initialised")
    with _pool.connection() as conn:  # commits, or rolls back on exception
        yield conn


def migrate(database_url: str) -> list[str]:
    """Apply pending migrations. Returns the names of those applied."""
    applied = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                                name       TEXT PRIMARY KEY,
                                applied_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
            done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in done:
                    continue
                # Each migration and its bookkeeping row commit together, or not at all.
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,))
    return applied


if __name__ == "__main__":  # python -m app.db  -> run migrations manually
    names = migrate(os.environ["DATABASE_URL"])
    print("applied:", names or "nothing (up to date)")
