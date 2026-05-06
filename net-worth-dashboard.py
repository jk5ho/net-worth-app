"""Streamlit entrypoint for the Interactive Net Worth Dashboard.

Run with:
    streamlit run net-worth-dashboard.py

This file is intentionally thin — all logic lives in the ``app`` package.
"""

from __future__ import annotations

import streamlit as st

from app.background import BackgroundImage
from app.currency import CurrencyConverter
from app.dashboard import Dashboard
from app.data_manager import DataManager
from app.database import init_db
from app.ledger import Ledger
from app.login_view import (
    current_user_id,
    is_logged_in,
    render_login_screen,
)
from app.sidebar import Sidebar


def main() -> None:
    st.set_page_config(
        page_title="Interactive Net Worth Dashboard",
        layout="wide",
        # Sidebar starts collapsed; Streamlit's built-in toggle acts as
        # the burger-menu trigger.
        initial_sidebar_state="collapsed",
    )

    # Idempotent — creates tables on first boot, no-op afterwards.
    init_db()

    BackgroundImage().apply()

    if not is_logged_in():
        render_login_screen()
        return

    st.title("💰 Interactive Net Worth Dashboard")

    data = DataManager(user_id=current_user_id())
    data.initialize_state()
    converter = CurrencyConverter()

    base_currency = Sidebar(data, converter).render()
    Dashboard(data, converter).render(base_currency)
    st.divider()
    Ledger(data).render()


main()
