"""Top-of-page dashboard: KPIs, trend line, allocation pies, provider bar."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.config import CLASS_COLORS
from app.currency import CurrencyConverter
from app.data_manager import DataManager


class Dashboard:
    """Renders metrics and Plotly charts using the graph snapshot DataFrame."""

    def __init__(self, data: DataManager, converter: CurrencyConverter) -> None:
        self.data = data
        self.converter = converter

    def render(self, base_currency: str) -> None:
        graph_df = self.data.graph_df
        graph_dates = self.data.date_columns(graph_df)

        selected_period, hide_balances = self._render_header(graph_dates)
        self._render_stale_warning()

        if not graph_dates or selected_period is None:
            st.warning("⚠️ No date columns found. Add a new date period in the sidebar.")
            return

        base_col = f"Base Currency ({base_currency})"
        display_df = graph_df.copy()
        display_df[base_col] = display_df.apply(
            lambda row: self.converter.to_base(row, selected_period, base_currency),
            axis=1,
        )

        self._render_metrics(display_df, base_col, base_currency, hide_balances)
        st.divider()
        self._render_trend(
            graph_df, graph_dates, base_currency, hide_balances, selected_period
        )
        self._render_allocation_charts(display_df, base_col)
        self._render_provider_bar(display_df, base_col)

    # ----- Header & status ------------------------------------------------

    def _render_header(self, graph_dates: list[str]) -> tuple[str | None, bool]:
        col_title, col_balances, col_bg, col_refresh = st.columns(
            [2, 1, 1, 1], vertical_alignment="bottom"
        )

        with col_title:
            st.subheader("Dashboard View")
            selected_period = self._render_period_selector(graph_dates)

        with col_balances:
            hide_balances = st.toggle("👁️ Hide Balances", value=False)

        with col_bg:
            # ``key="hide_background"`` lets ``BackgroundImage.apply()``
            # read the toggle from session state on the next rerun and
            # skip the CSS injection.
            st.toggle("🖼️ Hide Background", key="hide_background", value=False)

        with col_refresh:
            if st.button("🔄 Refresh Graphs", use_container_width=True):
                self.data.refresh_graph_snapshot()
                st.rerun()

        return selected_period, hide_balances

    @staticmethod
    def _render_period_selector(graph_dates: list[str]) -> str | None:
        """Render the period dropdown and return the selected date column.

        Latest period is shown first / selected by default. Selection is
        preserved across reruns via ``st.session_state``; if the stored
        value points at a period that has since been deleted, we fall
        back to the most recent one.
        """
        if not graph_dates:
            return None

        options = list(reversed(graph_dates))  # latest first
        if st.session_state.get("dashboard_period") not in options:
            st.session_state["dashboard_period"] = options[0]

        return st.selectbox(
            "Period",
            options=options,
            key="dashboard_period",
            label_visibility="collapsed",
        )

    def _render_stale_warning(self) -> None:
        if not self.data.grid_df.equals(self.data.graph_df):
            st.info(
                "💡 You have made changes in your ledger below. "
                "Click 'Refresh Graphs' to update these metrics."
            )

    # ----- Metrics --------------------------------------------------------

    @staticmethod
    def _format_currency(value: float, hide: bool) -> str:
        return "$******" if hide else f"${value:,.2f}"

    def _render_metrics(
        self,
        display_df: pd.DataFrame,
        base_col: str,
        base_currency: str,
        hide_balances: bool,
    ) -> None:
        liquid_mask = self.data.liquid_mask(display_df)
        positive = display_df[display_df[base_col] > 0][base_col]
        negative = display_df[display_df[base_col] < 0][base_col]
        liquid = display_df[(display_df[base_col] > 0) & liquid_mask][base_col]

        total_assets = positive.sum()
        total_liabs = negative.sum()
        total_net_worth = total_assets + total_liabs
        liquid_total = liquid.sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            f"Net Worth ({base_currency})",
            self._format_currency(total_net_worth, hide_balances),
        )
        m2.metric("Total Assets", self._format_currency(total_assets, hide_balances))
        m3.metric("Total Liabilities", self._format_currency(total_liabs, hide_balances))
        m4.metric("Liquid Assets", self._format_currency(liquid_total, hide_balances))

    # ----- Charts ---------------------------------------------------------

    def _render_trend(
        self,
        graph_df: pd.DataFrame,
        graph_dates: list[str],
        base_currency: str,
        hide_balances: bool,
        selected_period: str | None,
    ) -> None:
        history = []
        for date_col in graph_dates:
            converted = graph_df.apply(
                lambda row, dc=date_col: self.converter.to_base(row, dc, base_currency),
                axis=1,
            )
            history.append({"Date": date_col, "Net Worth": converted.sum()})

        hist_df = pd.DataFrame(history)
        fig = px.line(
            hist_df,
            x="Date",
            y="Net Worth",
            markers=True,
            title=f"Net Worth Growth ({base_currency})",
        )
        fig.update_traces(line_shape="spline", line=dict(width=3))

        if hide_balances:
            # Strip absolute values from the chart while keeping the
            # shape of the trend line readable. Apply hover updates
            # *before* adding the highlight marker so its trace stays
            # uncluttered.
            fig.update_yaxes(showticklabels=False, title_text="")
            fig.update_traces(hovertemplate="%{x}<extra></extra>")

        if selected_period and selected_period in graph_dates:
            self._add_period_highlight(fig, hist_df, selected_period)

        st.plotly_chart(fig, width="stretch")

    @staticmethod
    def _add_period_highlight(
        fig, hist_df: pd.DataFrame, selected_period: str
    ) -> None:
        """Overlay a gold marker on the trend line at ``selected_period``."""
        selected_value = (
            hist_df.loc[hist_df["Date"] == selected_period, "Net Worth"].iloc[0]
        )
        fig.add_scatter(
            x=[selected_period],
            y=[selected_value],
            mode="markers",
            marker=dict(
                size=18,
                color="#FFC107",
                line=dict(width=2, color="rgba(0, 0, 0, 0.65)"),
                symbol="circle",
            ),
            showlegend=False,
            hoverinfo="skip",
            name="Viewing",
        )

    def _render_allocation_charts(self, display_df: pd.DataFrame, base_col: str) -> None:
        c1, c2 = st.columns(2)
        with c1:
            assets_only = display_df[display_df[base_col] > 0]
            if not assets_only.empty:
                fig = px.pie(
                    assets_only,
                    values=base_col,
                    names="Class",
                    color="Class",
                    color_discrete_map=CLASS_COLORS,
                    title="Overall Asset Allocation",
                    hole=0.4,
                )
                st.plotly_chart(fig, width="stretch")

        with c2:
            liquid_only = display_df[
                (display_df[base_col] > 0) & self.data.liquid_mask(display_df)
            ]
            if not liquid_only.empty:
                fig = px.pie(
                    liquid_only,
                    values=base_col,
                    names="Class",
                    color="Class",
                    color_discrete_map=CLASS_COLORS,
                    title="Liquid Asset Allocation",
                    hole=0.4,
                )
                st.plotly_chart(fig, width="stretch")

    def _render_provider_bar(self, display_df: pd.DataFrame, base_col: str) -> None:
        liquid_only = display_df[self.data.liquid_mask(display_df)]
        if liquid_only.empty:
            return

        fig = px.bar(
            liquid_only,
            x="Provider",
            y=base_col,
            color="Class",
            color_discrete_map=CLASS_COLORS,
            title="Liquid Exposure by Provider",
        )
        st.plotly_chart(fig, width="stretch")
