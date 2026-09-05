from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

EXPECTED_TABLES = {"documents", "stories", "chapters", "platform_versions", "publish_records"}


@pytest.fixture
def alembic_config(tmp_path):
    """Alembic Config pointed at alembic.ini, with the DB URL overridden to a
    temporary SQLite file so migration tests never touch real project data."""
    db_path = tmp_path / "test_editorial.sqlite"
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config, db_path


def _table_names(db_path: Path) -> set[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_creates_all_editorial_tables(alembic_config):
    """Requirement 1.4: `alembic upgrade head` must create the full
    Document/Story/Chapter/PlatformVersion/PublishRecord schema."""
    config, db_path = alembic_config

    command.upgrade(config, "head")

    assert EXPECTED_TABLES.issubset(_table_names(db_path))


def test_downgrade_base_removes_all_editorial_tables(alembic_config):
    """Requirement 1.4: the migration must be revertible — `alembic downgrade base`
    removes every table it created, so a bad migration doesn't leave partial state."""
    config, db_path = alembic_config

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    assert EXPECTED_TABLES.isdisjoint(_table_names(db_path))
