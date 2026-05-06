"""Login + signup screen, plus session-state helpers used everywhere
that needs to know "is someone logged in?" / "who is this user?".

Auth state lives entirely in ``st.session_state`` — we keep the
``user_id`` (canonical identifier for DB scoping) and a copy of the
user's email/display name for the UI. The session does not persist
across browser refreshes, by design.
"""

from __future__ import annotations

import streamlit as st

from app.auth import AuthError, authenticate, create_user

USER_ID_KEY = "auth_user_id"
USER_EMAIL_KEY = "auth_user_email"
USER_DISPLAY_NAME_KEY = "auth_user_display_name"

# Per-user session-state keys we reset on login/logout so a returning
# user never sees a previous user's cached DataFrames or settings.
_USER_SCOPED_KEYS = (
    "grid_df",
    "graph_df",
    "dashboard_period",
    "_background_image_path",
    "hide_background",
)


# ----- Session helpers -------------------------------------------------


def is_logged_in() -> bool:
    return st.session_state.get(USER_ID_KEY) is not None


def current_user_id() -> int | None:
    return st.session_state.get(USER_ID_KEY)


def current_user_label() -> str:
    """Best-effort display name for the sidebar header."""
    return (
        st.session_state.get(USER_DISPLAY_NAME_KEY)
        or st.session_state.get(USER_EMAIL_KEY)
        or "Signed in"
    )


def _login(user) -> None:
    _clear_user_scoped_state()
    st.session_state[USER_ID_KEY] = user.id
    st.session_state[USER_EMAIL_KEY] = user.email
    st.session_state[USER_DISPLAY_NAME_KEY] = user.display_name


def logout() -> None:
    _clear_user_scoped_state()
    for key in (USER_ID_KEY, USER_EMAIL_KEY, USER_DISPLAY_NAME_KEY):
        st.session_state.pop(key, None)


def _clear_user_scoped_state() -> None:
    for key in _USER_SCOPED_KEYS:
        st.session_state.pop(key, None)


# ----- UI --------------------------------------------------------------


def render_login_screen() -> None:
    """Full-page login + signup view shown before any dashboard data
    is rendered or queried."""
    st.title("💰 Interactive Net Worth Dashboard")
    st.caption("Sign in to view and manage your ledger.")

    _, col, _ = st.columns([1, 2, 1])
    with col:
        sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])
        with sign_in_tab:
            _render_sign_in()
        with sign_up_tab:
            _render_sign_up()


def _render_sign_in() -> None:
    with st.form("sign_in_form", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="username")
        password = st.text_input(
            "Password", type="password", autocomplete="current-password"
        )
        submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submit:
        try:
            user = authenticate(email, password)
        except AuthError as exc:
            st.error(str(exc))
            return
        _login(user)
        st.rerun()


def _render_sign_up() -> None:
    with st.form("sign_up_form", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email")
        display_name = st.text_input(
            "Display name (optional)", autocomplete="name"
        )
        password = st.text_input(
            "Password", type="password", autocomplete="new-password"
        )
        confirm = st.text_input(
            "Confirm password", type="password", autocomplete="new-password"
        )
        submit = st.form_submit_button(
            "Create account", type="primary", use_container_width=True
        )

    if submit:
        try:
            user = create_user(email, password, confirm, display_name)
        except AuthError as exc:
            st.error(str(exc))
            return
        st.success(
            f"Account created for {user.email}. Welcome — you're now signed in."
        )
        _login(user)
        st.rerun()
