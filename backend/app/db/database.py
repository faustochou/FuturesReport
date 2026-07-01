"""
SQLAlchemy database engine + session factory.

URL priority:
  1. DATABASE_URL env var (PostgreSQL in production)
  2. SQLite under USER_DATA_DIR or uploads/ (source-code / dev fallback)
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Heroku / some providers emit postgres:// which SQLAlchemy 2 rejects
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    # Default: SQLite file alongside users.json
    data_dir = os.environ.get("USER_DATA_DIR", "").strip()
    if not data_dir:
        data_dir = os.path.join(os.path.dirname(__file__), "../../../uploads")
    os.makedirs(data_dir, exist_ok=True)
    return f"sqlite:///{os.path.join(data_dir, 'futuresreport.db')}"


def init_engine():
    global _engine, _SessionLocal

    url = _resolve_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    # Enable WAL mode for SQLite to reduce lock contention under Flask threads
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")

    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_engine():
    global _engine
    if _engine is None:
        init_engine()
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager that provides a transactional database session."""
    session: Session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables() -> None:
    """Create all tables that don't yet exist (idempotent)."""
    from . import models  # noqa: F401 – ensure models are registered
    Base.metadata.create_all(bind=get_engine())


def seed_subscription_tiers() -> None:
    """Insert the three default subscription tiers if the table is empty (idempotent)."""
    from .models import SubscriptionTier
    from datetime import datetime
    from sqlalchemy import select, func

    with get_db() as db:
        count = db.execute(
            select(func.count()).select_from(SubscriptionTier)
        ).scalar_one()
        if count > 0:
            return
        now = datetime.utcnow()
        db.add_all([
            SubscriptionTier(
                tier_code="lite",
                display_name="Lite",
                is_available=True,
                feature_flags={
                    "max_agents": 100,
                    "sim_runs_per_month": 10,
                    "report_export": True,
                },
                updated_at=now,
            ),
            SubscriptionTier(
                tier_code="premium",
                display_name="Premium",
                is_available=False,
                feature_flags={},
                updated_at=now,
            ),
            SubscriptionTier(
                tier_code="pro",
                display_name="Pro",
                is_available=False,
                feature_flags={},
                updated_at=now,
            ),
        ])


def ping() -> bool:
    """Return True if the database is reachable."""
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
