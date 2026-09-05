"""
SQLAlchemy session management for the editorial service. Points at the
same SQLite path Alembic manages (see alembic.ini's default
sqlalchemy.url) — a distinct file from the ingestion pipeline's
expedientes.sqlite (design.md Decision 3/4).
"""
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import DATA_DIR

EDITORIAL_SQLITE_PATH = DATA_DIR / "knowledge_base" / "editorial.sqlite"

EDITORIAL_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{EDITORIAL_SQLITE_PATH}")
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
