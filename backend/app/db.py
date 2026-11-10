from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute(f"PRAGMA journal_mode={settings.db_journal}")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns():
    """No Alembic for this app: add columns introduced after a database was created."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    ddl = col.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}'))
                    if col.default is not None:  # backfill existing rows with the column's default
                        arg = col.default.arg
                        if callable(arg):
                            if col.type.__class__.__name__ == "DateTime":
                                conn.execute(text(f'UPDATE {table.name} SET {col.name} = CURRENT_TIMESTAMP WHERE {col.name} IS NULL'))
                        else:
                            conn.execute(text(f'UPDATE {table.name} SET {col.name} = :v WHERE {col.name} IS NULL'), {"v": arg})
