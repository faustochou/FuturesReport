"""
SQLAlchemy ORM models – users, per-user LLM credentials, and subscriptions.
"""

import json
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, TEXT

from .database import Base


# ---------------------------------------------------------------------------
# Custom JSON column type (works on both SQLite and PostgreSQL)
# ---------------------------------------------------------------------------

class _JsonColumn(TypeDecorator):
    """Store a dict/list as JSON text; retrieves as Python object."""
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return "{}"
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if not value:
            return {}
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_user_id() -> str:
    return f"user_{secrets.token_urlsafe(12)}"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_new_user_id
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    llm_config: Mapped["LlmConfig"] = relationship(
        "LlmConfig",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    subscription: Mapped[Optional["UserSubscription"]] = relationship(
        "UserSubscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    simulation_records: Mapped[List["SimulationRecord"]] = relationship(
        "SimulationRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# LlmConfig
# ---------------------------------------------------------------------------

class LlmConfig(Base):
    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    api_key_cipher: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hint: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="llm_config")


# ---------------------------------------------------------------------------
# SubscriptionTier  (seeded: lite / premium / pro)
# ---------------------------------------------------------------------------

class SubscriptionTier(Base):
    """Static tier catalogue.  Rows are seeded by the migration; admins can
    toggle is_available and edit stripe_price_id at runtime via the admin API."""
    __tablename__ = "subscription_tiers"

    tier_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # JSON dict: {"max_agents": 100, "sim_runs_per_month": 10, ...}
    feature_flags: Mapped[Dict[str, Any]] = mapped_column(
        _JsonColumn, nullable=False, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    subscriptions: Mapped[List["UserSubscription"]] = relationship(
        "UserSubscription", back_populates="tier"
    )

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# UserSubscription  (one row per user; upserted on Stripe webhook)
# ---------------------------------------------------------------------------

class UserSubscription(Base):
    """Tracks the active Stripe subscription for a user.
    One row per user (unique on user_id).  Updated by webhook events."""
    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tier_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("subscription_tiers.tier_code"),
        nullable=False,
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    # Mirrors Stripe subscription.status: active / canceled / past_due /
    # incomplete / incomplete_expired / trialing / unpaid
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="subscription")
    tier: Mapped["SubscriptionTier"] = relationship(
        "SubscriptionTier", back_populates="subscriptions"
    )

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# SimulationRecord  (one row per simulation run, tied to the user who started it)
# ---------------------------------------------------------------------------

class SimulationRecord(Base):
    """Persistent log of every simulation run. Kept for 30 days then purged."""
    __tablename__ = "simulation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    simulation_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Stored as JSON array of filename strings, e.g. ["report.pdf", "data.txt"]
    report_filenames: Mapped[Any] = mapped_column(_JsonColumn, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # "running" | "completed" | "failed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="simulation_records")
