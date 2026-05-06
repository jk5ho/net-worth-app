"""SQLAlchemy engine, ORM models and session helpers.

SQLite is the default backend so the app boots with zero configuration.
For production, set ``DATABASE_URL`` to any SQLAlchemy-supported URL
(e.g. ``postgresql+psycopg://user:pw@host/db``).

Two tables:

* ``users`` — one row per account, plus an ordered ``periods`` list.
* ``ledger_rows`` — one row per ledger entry, scoped by ``user_id``.
  Period values live inside a ``values`` JSON column keyed by period
  label so add/remove-period operations stay O(1) per row.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import streamlit as st
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Ordered list of period labels (e.g. ["3/30", "4/23"]) so the
    # ledger reconstructs the same column ordering across sessions.
    periods: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    rows: Mapped[list["LedgerRow"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="LedgerRow.position",
    )


class LedgerRow(Base):
    __tablename__ = "ledger_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    provider: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(64), default="Personal")
    asset_class: Mapped[str] = mapped_column(String(64), default="")
    product: Mapped[str] = mapped_column(String(255), default="")
    details: Mapped[str] = mapped_column(String(255), default="")
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    # { "3/30": 287868.00, "4/23": 287868.00 }
    values: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="rows")


# ----- Engine + session plumbing ---------------------------------------


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """Return a process-wide SQLAlchemy engine.

    ``st.cache_resource`` ensures we don't churn engines (and SQLite
    file handles) on every Streamlit rerun.
    """
    connect_args: dict = {}
    if DATABASE_URL.startswith("sqlite"):
        # Allow the engine to be used from Streamlit's worker threads.
        connect_args["check_same_thread"] = False
    return create_engine(DATABASE_URL, future=True, connect_args=connect_args)


@st.cache_resource(show_spinner=False)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session that commits on success and
    rolls back on exception."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ----- Lifecycle ------------------------------------------------------


def init_db() -> None:
    """Create tables if they do not yet exist. Idempotent and safe to
    call on every app boot."""
    Base.metadata.create_all(get_engine())


# ----- Convenience accessors used by the auth + data layers -----------


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.execute(
        select(User).where(User.email == email.lower().strip())
    ).scalar_one_or_none()


def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)
