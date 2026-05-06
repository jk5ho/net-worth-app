"""DB-backed persistence and Streamlit session-state management.

Each ``DataManager`` instance is scoped to a single ``user_id`` — the
same underlying ``users``/``ledger_rows`` tables hold every account's
data, but every read/write filters by user so accounts are completely
isolated from one another.

Public API mirrors the previous CSV-backed version, so the rest of the
app (sidebar, dashboard, ledger) didn't have to change:

* ``initialize_state()`` hydrates session state on first hit.
* ``load() -> DataFrame``      — pull latest from DB
* ``save(df)``                  — persist DataFrame back to DB
* ``grid_df`` / ``graph_df``    — session-state-backed views
* ``date_columns(df)`` / ``liquid_mask(df)`` / ``latest_date(df)``
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st
from sqlalchemy import delete, select

from app.config import BASE_COLS, LIQUID_CLASSES
from app.database import LedgerRow, User, get_user, session_scope


class DataManager:
    GRID_KEY = "grid_df"
    GRAPH_KEY = "graph_df"

    def __init__(self, user_id: int) -> None:
        if user_id is None:
            raise ValueError("DataManager requires a logged-in user_id")
        self.user_id = int(user_id)

    # ----- Disk I/O -------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Build a DataFrame from the current user's ``ledger_rows``."""
        with session_scope() as session:
            user = get_user(session, self.user_id)
            if user is None:
                return pd.DataFrame(columns=BASE_COLS)

            rows = session.execute(
                select(LedgerRow)
                .where(LedgerRow.user_id == self.user_id)
                .order_by(LedgerRow.position, LedgerRow.id)
            ).scalars().all()

            periods: List[str] = list(user.periods or [])

            base_data = [
                {
                    "Provider": r.provider or "",
                    "Type": r.type or "Personal",
                    "Class": r.asset_class or "",
                    "Product": r.product or "",
                    "Details": r.details or "",
                    "Currency": r.currency or "USD",
                }
                for r in rows
            ]

        df = pd.DataFrame(base_data, columns=BASE_COLS)
        for period in periods:
            df[period] = [
                self._coerce_numeric((r.values or {}).get(period, 0.0))
                for r in rows
            ]
        return df

    def save(self, df: pd.DataFrame) -> None:
        """Persist ``df`` as the user's ledger.

        Replaces the user's rows wholesale inside a single transaction
        so the on-disk state always matches the DataFrame the user sees.
        """
        periods = self.date_columns(df)
        rows_payload = [self._row_payload(row, periods) for _, row in df.iterrows()]

        with session_scope() as session:
            user = get_user(session, self.user_id)
            if user is None:
                raise RuntimeError(f"User {self.user_id} no longer exists")

            user.periods = periods

            session.execute(
                delete(LedgerRow).where(LedgerRow.user_id == self.user_id)
            )
            for position, payload in enumerate(rows_payload):
                session.add(
                    LedgerRow(
                        user_id=self.user_id,
                        position=position,
                        **payload,
                    )
                )

    # ----- Session state --------------------------------------------------

    def initialize_state(self) -> None:
        if self.GRID_KEY not in st.session_state:
            initial = self.load()
            st.session_state[self.GRID_KEY] = initial.copy()
            st.session_state[self.GRAPH_KEY] = initial.copy()

    @property
    def grid_df(self) -> pd.DataFrame:
        return st.session_state[self.GRID_KEY]

    @grid_df.setter
    def grid_df(self, value: pd.DataFrame) -> None:
        st.session_state[self.GRID_KEY] = value

    @property
    def graph_df(self) -> pd.DataFrame:
        return st.session_state[self.GRAPH_KEY]

    @graph_df.setter
    def graph_df(self, value: pd.DataFrame) -> None:
        st.session_state[self.GRAPH_KEY] = value

    def refresh_graph_snapshot(self) -> None:
        self.graph_df = self.grid_df.copy()

    # ----- Helpers --------------------------------------------------------

    @staticmethod
    def date_columns(df: pd.DataFrame) -> List[str]:
        return [col for col in df.columns if col not in BASE_COLS]

    @classmethod
    def latest_date(cls, df: pd.DataFrame) -> str | None:
        cols = cls.date_columns(df)
        return cols[-1] if cols else None

    @staticmethod
    def liquid_mask(df: pd.DataFrame) -> pd.Series:
        if "Class" not in df.columns:
            return pd.Series(dtype=bool)
        return df["Class"].isin(LIQUID_CLASSES)

    # ----- Internals ------------------------------------------------------

    @staticmethod
    def _coerce_numeric(raw) -> float:
        try:
            if raw is None or raw == "":
                return 0.0
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _row_payload(cls, row: pd.Series, periods: List[str]) -> dict:
        values = {p: cls._coerce_numeric(row.get(p, 0.0)) for p in periods}
        return {
            "provider": str(row.get("Provider", "") or ""),
            "type": str(row.get("Type", "Personal") or "Personal"),
            "asset_class": str(row.get("Class", "") or ""),
            "product": str(row.get("Product", "") or ""),
            "details": str(row.get("Details", "") or ""),
            "currency": str(row.get("Currency", "USD") or "USD"),
            "values": values,
        }
