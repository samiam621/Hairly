"""The pool reuses database connections instead of opening a new connection for every request."""

from psycopg_pool import ConnectionPool

from backend.core.config import settings


pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=5,
    open=False,
    # Supabase's transaction pooler (port 6543) can't keep prepared statements between transactions.
    kwargs={"prepare_threshold": None},
    # The pooler drops idle connections; test each one before handing it out.
    check=ConnectionPool.check_connection,
)
