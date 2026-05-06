"""Sidebar UI: account, data management, settings, periods, add-row form."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.config import (
    BASE_COLS,
    CURRENCY_OPTIONS,
    LIQUID_CLASSES,
    NON_LIQUID_CLASSES,
    TYPE_OPTIONS,
)
from app.currency import CurrencyConverter
from app.data_manager import DataManager
from app.login_view import current_user_label, logout


class Sidebar:
    """Renders the Streamlit sidebar and mutates ``DataManager`` state in place."""

    def __init__(self, data: DataManager, converter: CurrencyConverter) -> None:
        self.data = data
        self.converter = converter

    def render(self) -> str:
        """Render the sidebar and return the user's chosen base currency."""
        with st.sidebar:
            self._render_account()
            st.divider()
            self._render_data_management()
            st.divider()
            base_currency = self._render_global_settings()
            st.divider()
            self._render_period_management()
            st.divider()
            self._render_add_row_form()
        return base_currency

    # ----- Sections -------------------------------------------------------

    def _render_account(self) -> None:
        st.header("👤 Account")
        st.caption(f"Signed in as **{current_user_label()}**")
        if st.button("Sign out", use_container_width=True):
            logout()
            st.rerun()

    def _render_data_management(self) -> None:
        st.header("💾 Data Management")

        if st.button("Reload from database"):
            self.data.grid_df = self.data.load()
            self.data.refresh_graph_snapshot()
            st.success("✅ Reloaded ledger from the database.")
            st.rerun()

        if st.button("Save all changes", type="primary"):
            self.data.save(self.data.grid_df)
            st.success("✅ Saved to the database.")

        with st.expander("Import / Export CSV"):
            uploaded = st.file_uploader(
                "Import CSV (replaces current ledger)",
                type=["csv"],
                accept_multiple_files=False,
                key="csv_uploader",
            )
            if uploaded is not None:
                self._import_csv(uploaded)

            grid_df = self.data.grid_df
            if not grid_df.empty:
                csv_bytes = grid_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download current ledger as CSV",
                    data=csv_bytes,
                    file_name="net_worth_data.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    def _import_csv(self, uploaded) -> None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as exc:  # pragma: no cover - user-input dependent
            st.error(f"Could not read CSV: {exc}")
            return

        df = self._normalise_imported_df(df)
        if df is None:
            return

        self.data.grid_df = df
        self.data.save(df)
        self.data.refresh_graph_snapshot()
        # Reset the uploader so the same file isn't re-imported on next rerun.
        st.session_state.pop("csv_uploader", None)
        st.success(f"✅ Imported {len(df)} rows and saved to the database.")
        st.rerun()

    @staticmethod
    def _normalise_imported_df(df: pd.DataFrame) -> pd.DataFrame | None:
        """Drop legacy columns, ensure all base columns exist, and
        coerce period values to numeric. Returns ``None`` (and surfaces
        an error) if the CSV is unrecognisable."""
        # Drop legacy artefacts: AgGrid junk + the deprecated Detail/Liquid cols.
        junk = [c for c in df.columns if c.startswith("::") or c.startswith("_")]
        for legacy in ("Detail", "Liquid"):
            if legacy in df.columns:
                junk.append(legacy)
        if junk:
            df = df.drop(columns=junk)

        if "Provider" not in df.columns:
            st.error("CSV is missing a `Provider` column — nothing to import.")
            return None

        # Backfill any missing base columns so downstream code is happy.
        for col in BASE_COLS:
            if col not in df.columns:
                df[col] = "" if col != "Type" else "Personal"

        text_cols = ["Provider", "Type", "Class", "Product", "Details", "Currency"]
        df[text_cols] = df[text_cols].fillna("")
        df["Type"] = df["Type"].replace(["Assets", "Liabilities"], "Personal")

        # Re-order columns: base first, then date columns in source order.
        date_cols = [c for c in df.columns if c not in BASE_COLS]
        for dc in date_cols:
            df[dc] = pd.to_numeric(df[dc], errors="coerce").fillna(0.0)
        return df[BASE_COLS + date_cols].reset_index(drop=True)

    def _render_global_settings(self) -> str:
        st.header("Global Settings")
        base_currency = st.selectbox(
            "Select Base Dashboard Currency", CURRENCY_OPTIONS, index=0
        )

        with st.expander("📈 View Live Exchange Rates"):
            st.caption("Rates relative to 1 USD. Updates hourly.")
            st.json(self.converter.rates)

        return base_currency

    def _render_period_management(self) -> None:
        st.header("Manage Date Periods")

        date_cols = self.data.date_columns(self.data.grid_df)
        latest = date_cols[-1] if date_cols else None

        new_label = st.text_input("New Period (e.g., 3/30)")
        if st.button("Create Period"):
            if new_label and new_label not in self.data.grid_df.columns:
                seed = self.data.grid_df[latest] if latest else 0.0
                self.data.grid_df[new_label] = seed
                st.rerun()

        if date_cols:
            st.write("---")
            remove_label = st.selectbox(
                "Remove an Existing Period", [""] + date_cols
            )
            if st.button("Delete Period") and remove_label:
                self.data.grid_df = self.data.grid_df.drop(columns=[remove_label])
                st.rerun()

    def _render_add_row_form(self) -> None:
        st.header("Add New Row Entry")

        # The radio lives outside ``st.form`` so the form re-renders with
        # the right fields the moment the user toggles it.
        kind = st.radio(
            "Entry kind",
            ("Investment (liquid)", "Asset / Liability (non-liquid)"),
            horizontal=False,
        )
        is_liquid = kind.startswith("Investment")

        date_cols = self.data.date_columns(self.data.grid_df)
        latest = date_cols[-1] if date_cols else None

        form_key = "liquid_entry_form" if is_liquid else "non_liquid_entry_form"
        with st.form(form_key, clear_on_submit=True):
            provider = st.text_input("Provider")
            type_ = st.selectbox("Type", TYPE_OPTIONS)

            if is_liquid:
                class_ = st.selectbox("Class", LIQUID_CLASSES)
                product = st.text_input("Product")
                details = ""
            else:
                class_ = st.selectbox("Class", NON_LIQUID_CLASSES)
                product = ""
                details = st.text_input("Details")

            currency = st.selectbox("Currency", CURRENCY_OPTIONS)
            value = st.number_input(
                f"Local Value ({latest or 'Latest'})", step=100.0
            )

            if st.form_submit_button("Add Row"):
                # Liabilities are stored as negative numbers.
                if class_ == "Liability":
                    value = -abs(value)

                row = {
                    "Provider": provider,
                    "Type": type_,
                    "Class": class_,
                    "Product": product,
                    "Details": details,
                    "Currency": currency,
                }
                for dc in date_cols:
                    row[dc] = 0.0
                if latest:
                    row[latest] = value

                self.data.grid_df = pd.concat(
                    [self.data.grid_df, pd.DataFrame([row])], ignore_index=True
                )
                st.rerun()
