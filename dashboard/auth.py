"""
dashboard/auth.py — Authentication UI for Smart Cloud Optimizer.

Provides login/register forms, session management, and demo mode entry.
"""
import streamlit as st

from dashboard.components import get_db_connection
from storage.db import authenticate_user, register_user


# ==============================================================================
# Session State Management
# ==============================================================================

def init_session_state() -> None:
    """Set default auth session state keys (safe to call repeatedly)."""
    defaults = {
        "authenticated": False,
        "auth_user_id": "",
        "user_email": "",
        "user_profile_name": "",
        "demo_mode": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_authenticated() -> bool:
    """Return True if the user is logged in or in demo mode."""
    return st.session_state.get("authenticated", False)


def login(email: str, password: str) -> tuple[bool, str]:
    """Attempt login. Returns (success, message)."""
    if not email or not password:
        return False, "Please enter both email and password."

    conn = get_db_connection()
    user = authenticate_user(conn, email, password)
    if user is None:
        return False, "Invalid email or password."

    st.session_state.authenticated = True
    st.session_state.auth_user_id = user["user_id"]
    st.session_state.user_email = user["email"]
    st.session_state.user_profile_name = user["profile_name"]
    st.session_state.demo_mode = False
    return True, "Login successful."


def logout() -> None:
    """Clear auth state and rerun."""
    keys = [
        "authenticated", "auth_user_id", "user_email",
        "user_profile_name", "demo_mode", "selected_user",
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def register(email: str, password: str, confirm_password: str,
             profile_name: str) -> tuple[bool, str]:
    """Attempt registration. Returns (success, message)."""
    if not email or not password:
        return False, "Email and password are required."
    if password != confirm_password:
        return False, "Passwords do not match."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    conn = get_db_connection()
    try:
        user_id = register_user(conn, email, password, profile_name)
    except ValueError as exc:
        return False, str(exc)

    # Auto-login after registration
    st.session_state.authenticated = True
    st.session_state.auth_user_id = user_id
    st.session_state.user_email = email
    st.session_state.user_profile_name = profile_name or email.split("@")[0]
    st.session_state.demo_mode = False
    return True, "Account created successfully."


def _enter_demo_mode() -> None:
    """Log in as the demo user (demo@cis.asu.edu.eg)."""
    ok, msg = login("demo@cis.asu.edu.eg", "password")
    if ok:
        st.session_state.demo_mode = True


# ==============================================================================
# Auth Page Renderer
# ==============================================================================

def render_auth_page() -> None:
    """Render the login / register page with demo mode option."""
    # Centered layout
    _col_left, col_center, _col_right = st.columns([1, 2, 1])

    with col_center:
        st.markdown("## Welcome to Smart Cloud Optimizer")
        st.markdown("Sign in to manage your AWS cost optimization.")
        st.markdown("")

        tab_login, tab_register = st.tabs(["Login", "Register"])

        # -- Login tab -------------------------------------------------------
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Sign In", use_container_width=True,
                )

            if submitted:
                ok, msg = login(email, password)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        # -- Register tab ----------------------------------------------------
        with tab_register:
            with st.form("register_form"):
                reg_name = st.text_input("Display Name")
                reg_email = st.text_input("Email")
                reg_pw = st.text_input("Password", type="password")
                reg_pw2 = st.text_input("Confirm Password", type="password")
                reg_submitted = st.form_submit_button(
                    "Create Account", use_container_width=True,
                )

            if reg_submitted:
                ok, msg = register(reg_email, reg_pw, reg_pw2, reg_name)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        # -- Demo mode -------------------------------------------------------
        st.markdown("---")
        st.markdown("**Just exploring?**")
        if st.button("Try Demo Mode", use_container_width=True):
            _enter_demo_mode()
            st.rerun()

        st.caption(
            "Demo mode uses synthetic AWS data — no account required."
        )
