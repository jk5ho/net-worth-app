"""Editable AgGrid ledgers.

The ledger is split into two tables that share one underlying DataFrame
but show different columns:

* **Liquid Assets** (Class ∈ ``LIQUID_CLASSES``) — shows
  ``Provider | Type | Class | Product | Currency | <dates>``.
* **Non-Liquid Assets / Liabilities**
  (Class ∈ ``NON_LIQUID_CLASSES``) — shows
  ``Provider | Type | Details | Currency | <dates>``.

The hidden columns are still tracked by AgGrid so drag-reordering and
edits in one view never wipe data in the other view.
"""

from __future__ import annotations

from typing import Iterable, List

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from app.config import (
    BASE_COLS,
    CLASS_OPTIONS,
    CURRENCY_OPTIONS,
    LIQUID_CLASSES,
    NON_LIQUID_CLASSES,
    TYPE_OPTIONS,
)
from app.data_manager import DataManager

LIQUID_HIDDEN_COLS = {"Details"}
NON_LIQUID_HIDDEN_COLS = {"Class", "Product"}

# Renders period-column values as ``$xxx,xxx.xx`` (or ``-$xxx,xxx.xx``
# for liabilities) at display time. The underlying cell value stays
# numeric, so editing and downstream pandas math still work.
CURRENCY_FORMATTER = JsCode(
    """
    function(params) {
        if (params.value === null || params.value === undefined || params.value === '') {
            return '';
        }
        const num = Number(params.value);
        if (Number.isNaN(num)) return params.value;
        const formatted = Math.abs(num).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return num < 0 ? '-$' + formatted : '$' + formatted;
    }
    """
)


class Ledger:
    """Renders the two AgGrid tables and writes edits back to state."""

    def __init__(self, data: DataManager) -> None:
        self.data = data

    def render(self) -> None:
        grid_df = self.data.grid_df
        date_cols = self.data.date_columns(grid_df)

        liquid_mask = self.data.liquid_mask(grid_df)
        liquid_df = grid_df[liquid_mask].reset_index(drop=True)
        non_liquid_df = grid_df[~liquid_mask].reset_index(drop=True)

        st.subheader("Liquid Assets")
        liquid_response = self._render_grid(
            liquid_df,
            key="liquid_grid",
            hidden_cols=LIQUID_HIDDEN_COLS,
            class_options=LIQUID_CLASSES,
        )

        st.subheader("Non-Liquid Assets / Liabilities")
        non_liquid_response = self._render_grid(
            non_liquid_df,
            key="non_liquid_grid",
            hidden_cols=NON_LIQUID_HIDDEN_COLS,
            class_options=NON_LIQUID_CLASSES,
        )

        merged = self._merge_responses(
            liquid_response, non_liquid_response, date_cols
        )
        if merged is None:
            return

        current = self.data.grid_df.reset_index(drop=True)
        if not merged.equals(current):
            self.data.grid_df = merged

    # ----- Grid rendering -------------------------------------------------

    def _render_grid(
        self,
        df: pd.DataFrame,
        key: str,
        hidden_cols: Iterable[str],
        class_options: List[str],
    ):
        if df.empty:
            st.caption("_No rows yet — add one from the sidebar._")
            return None

        return AgGrid(
            df,
            gridOptions=self._build_grid_options(df, hidden_cols, class_options),
            update_mode=GridUpdateMode.MODEL_CHANGED,
            fit_columns_on_grid_load=False,
            height=400,
            theme="streamlit",
            key=key,
            # Required so AgGrid actually runs the ``JsCode`` value
            # formatter on the period columns instead of treating it
            # as plain text.
            allow_unsafe_jscode=True,
        )

    @staticmethod
    def _build_grid_options(
        df: pd.DataFrame,
        hidden_cols: Iterable[str],
        class_options: List[str],
    ) -> dict:
        hidden = set(hidden_cols)
        builder = GridOptionsBuilder.from_dataframe(df)
        builder.configure_default_column(editable=True, resizable=True, minWidth=120)

        # Pin the first visible base column and give it the row-drag handle.
        first_visible_done = False
        for col in BASE_COLS:
            if col not in df.columns:
                continue
            if col in hidden:
                builder.configure_column(col, hide=True)
                continue
            if not first_visible_done:
                builder.configure_column(col, pinned="left", rowDrag=True)
                first_visible_done = True
            else:
                builder.configure_column(col, pinned="left")

        builder.configure_column(
            "Type",
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": TYPE_OPTIONS},
        )
        builder.configure_column(
            "Class",
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": class_options},
        )
        builder.configure_column(
            "Currency",
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": CURRENCY_OPTIONS},
        )

        # Period columns (everything that isn't a base column) get the
        # currency formatter and right-aligned numeric treatment.
        for col in df.columns:
            if col in BASE_COLS:
                continue
            builder.configure_column(
                col,
                type=["numericColumn"],
                valueFormatter=CURRENCY_FORMATTER,
            )

        options = builder.build()
        options["rowDragManaged"] = True
        options["animateRows"] = True
        return options

    # ----- Merge responses back into a single ledger ---------------------

    def _merge_responses(
        self, liquid_response, non_liquid_response, date_cols: List[str]
    ) -> pd.DataFrame | None:
        liquid = self._extract_frame(liquid_response, date_cols)
        non_liquid = self._extract_frame(non_liquid_response, date_cols)

        if liquid is None and non_liquid is None:
            return None

        # Use empty templates for sides that did not render so concat keeps
        # the canonical column ordering.
        template = self.data.grid_df.iloc[0:0]
        liquid = template.copy() if liquid is None else liquid
        non_liquid = template.copy() if non_liquid is None else non_liquid

        merged = pd.concat([liquid, non_liquid], ignore_index=True)
        # Preserve original column ordering of grid_df.
        ordered = [c for c in self.data.grid_df.columns if c in merged.columns]
        return merged[ordered].reset_index(drop=True)

    @staticmethod
    def _extract_frame(response, date_cols: List[str]) -> pd.DataFrame | None:
        if response is None:
            return None
        data = response["data"]
        if not isinstance(data, pd.DataFrame) or data.empty:
            return None

        # AgGrid sometimes injects internal columns prefixed with "::" or "_".
        junk = [c for c in data.columns if c.startswith("::") or c.startswith("_")]
        if junk:
            data = data.drop(columns=junk)

        for dc in date_cols:
            if dc in data.columns:
                data[dc] = pd.to_numeric(data[dc], errors="coerce").fillna(0.0)

        return data.reset_index(drop=True)
