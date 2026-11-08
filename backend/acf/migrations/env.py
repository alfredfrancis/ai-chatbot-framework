"""Alembic environment. Migrations run from `acf.db.migrate()` at startup (a connection is passed in), or
from the command line in backend/ (`alembic revision --autogenerate -m "…"`), which uses ACF_DB_URL."""

from alembic import context

from acf import config, db

target_metadata = db.Base.metadata


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite can't ALTER most things; batch mode copies the table instead
        compare_type=True,
    )


connection = context.config.attributes.get("connection")
if connection is not None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()
else:
    from sqlalchemy import create_engine

    config.reload_settings()
    engine = create_engine(db.normalize_url(config.settings.db_url))
    with engine.begin() as conn:
        _configure(conn)
        context.run_migrations()
