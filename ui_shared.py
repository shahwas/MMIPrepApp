"""
Shared UI helpers: authentication gate, sidebar, global CSS.
Every page calls  require_login()  at the top — if no user is selected
the visitor sees the profile picker and execution stops.
"""

import streamlit as st
from db import (
    init_db, get_all_users, create_user, get_user_by_id,
    get_user_skills, SKILL_NAMES, count_questions,
    get_or_create_user_from_oidc, create_user_with_password, verify_password_for_user,
)
import os
from srs import get_study_stats

AVATARS = ["🧑‍⚕️", "👩‍⚕️", "👨‍⚕️", "🩺", "🧬", "🔬", "💊", "🏥", "❤️‍🩹", "🌟"]


# ─── Global CSS ──────────────────────────────────────────────────

GLOBAL_CSS = """
<style>
    /* ── Typography ────────────────────────────── */
    .main-header {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
        letter-spacing: -0.02em;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #888;
        margin-top: -8px;
        margin-bottom: 28px;
    }

    /* ── Cards / Metrics ──────────────────────── */
    .stat-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 100%);
        border-radius: 14px;
        padding: 22px 18px;
        text-align: center;
        border: 1px solid rgba(102, 126, 234, 0.12);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.15);
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #333;
        line-height: 1.1;
    }
    .stat-label {
        font-size: 0.82rem;
        color: #777;
        margin-top: 6px;
    }

    /* ── Skill Bars ───────────────────────────── */
    .skill-bar-outer {
        height: 8px;
        border-radius: 4px;
        background: #e0e0e0;
        margin-bottom: 6px;
        overflow: hidden;
    }
    .skill-bar-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.4s ease;
    }
    .skill-unknown {
        font-size: 0.78rem;
        color: #aaa;
        font-style: italic;
    }

    /* ── Action Cards ─────────────────────────── */
    .action-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 20px;
        border-left: 4px solid #667eea;
        margin-bottom: 12px;
    }
    .action-card h4 { margin: 0 0 6px 0; }
    .action-card small { color: #666; }

    /* ── Sidebar ──────────────────────────────── */
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown { color: #e0e0e0; }
    div[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12); }
    .sidebar-user {
        background: rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
        text-align: center;
    }
    .sidebar-user .avatar { font-size: 2rem; }
    .sidebar-user .name {
        color: #fff;
        font-weight: 600;
        font-size: 1rem;
        margin-top: 2px;
    }

    /* ── Profile Picker ──────────────────────── */
    .profile-card {
        background: linear-gradient(135deg, #f8f9ff 0%, #eef1ff 100%);
        border-radius: 14px;
        padding: 28px 24px;
        text-align: center;
        border: 2px solid transparent;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .profile-card:hover {
        border-color: #667eea;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.2);
    }
    .profile-card .avatar { font-size: 3rem; }
    .profile-card .name {
        font-weight: 700;
        font-size: 1.1rem;
        margin-top: 8px;
        color: #333;
    }

    /* ── Empty States ─────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #aaa;
    }
    .empty-state .icon { font-size: 3rem; margin-bottom: 12px; }
    .empty-state p { font-size: 0.95rem; }

    /* ── Misc polish ─────────────────────────── */
    .stTextArea textarea { border-radius: 10px; }
    .stButton > button { border-radius: 8px; }
    div.stProgress > div > div { border-radius: 8px; }
</style>
"""


def inject_css():
    """Inject the global CSS. Call once per page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ─── Auth / Profile Gate ─────────────────────────────────────────

def _show_profile_picker():
    """Full-page profile picker / creator."""
    inject_css()

    st.markdown('<p class="main-header">MMI Prep</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">AI-powered MMI interview coaching — choose your profile to begin.</p>', unsafe_allow_html=True)

    # If Streamlit OIDC is configured, use it. Otherwise show guidance.
    try:
        # st.user is provided by Streamlit auth
        if not hasattr(st, "user") or not st.user.is_logged_in:
            st.markdown("### Sign in")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Sign in with Google / OIDC**")
                if st.button("Sign in with Google"):
                    # Redirect to configured OIDC provider (uses [auth] in secrets.toml)
                    st.login()
                st.markdown("---")
                st.info("This app supports Google sign-in. Configure providers in Streamlit Secrets.")

            with col2:
                st.markdown("**Sign in with email**")
                with st.form("local_login"):
                    email = st.text_input("Email / Display name")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Sign in")
                    if submitted:
                        try:
                            user = verify_password_for_user(email, password)
                        except Exception:
                            user = None
                        if user:
                            st.session_state["user_id"] = user["id"]
                            st.session_state["user_name"] = user["display_name"]
                            st.session_state["user_avatar"] = user.get("avatar", "🩺")
                            st.experimental_rerun()
                        else:
                            st.error("Invalid credentials or user does not exist.")

                st.markdown("---")
                st.markdown("**Create an account**")
                with st.form("local_register"):
                    reg_name = st.text_input("Display name", key="reg_name")
                    reg_password = st.text_input("Password", type="password", key="reg_pw")
                    reg_password2 = st.text_input("Confirm password", type="password", key="reg_pw2")
                    reg_sub = st.form_submit_button("Create account")
                    if reg_sub:
                        if not reg_name or not reg_password:
                            st.error("Please provide a display name and password.")
                        elif reg_password != reg_password2:
                            st.error("Passwords do not match.")
                        else:
                            try:
                                uid = create_user_with_password(reg_name, reg_password)
                                user = get_user_by_id(uid)
                                st.session_state["user_id"] = user["id"]
                                st.session_state["user_name"] = user["display_name"]
                                st.session_state["user_avatar"] = user.get("avatar", "🩺")
                                st.success("Account created and signed in.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Could not create account: {e}")

            st.stop()

        # Map the OIDC identity to a local user row
        ident = st.user
        # prefer `sub`, fallback to email/name
        external_id = getattr(ident, "sub", None) or getattr(ident, "id", None) or getattr(ident, "email", None)
        display_name = getattr(ident, "name", None) or getattr(ident, "email", None) or external_id
        avatar = "🩺"
        if not external_id:
            st.error("OIDC provider did not return a usable identifier (sub/email).")
            st.stop()

        user = get_or_create_user_from_oidc(external_id, display_name, avatar)
        st.session_state["user_id"] = user["id"]
        st.session_state["user_name"] = user["display_name"]
        st.session_state["user_avatar"] = user.get("avatar", "🩺")
        # allow page to continue
        return
    except Exception:
        st.error("Authentication is not configured. Add OIDC settings to `.streamlit/secrets.toml` and install streamlit[auth].")
        st.stop()


def require_login():
    """
    Call at the top of every page. If no user is selected shows the
    profile picker and calls st.stop(). Returns (user_id, user_name).
    """
    init_db()

    if "user_id" not in st.session_state:
        _show_profile_picker()
        st.stop()

    # Validate user still exists
    user = get_user_by_id(st.session_state["user_id"])
    if not user:
        for k in ("user_id", "user_name", "user_avatar"):
            st.session_state.pop(k, None)
        _show_profile_picker()
        st.stop()

    return st.session_state["user_id"], st.session_state["user_name"]


# ─── Shared Sidebar ──────────────────────────────────────────────

def render_sidebar(active: str = "home"):
    """Render the sidebar with user info + nav. `active` highlights the page."""
    user_id = st.session_state.get("user_id", "default")
    user_name = st.session_state.get("user_name", "Guest")
    user_avatar = st.session_state.get("user_avatar", "🩺")

    with st.sidebar:
        # User pill
        st.markdown(
            f'<div class="sidebar-user">'
            f'<div class="avatar">{user_avatar}</div>'
            f'<div class="name">{user_name}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Nav links
        pages = [
            ("home",    "app.py",            "🏠 Dashboard"),
            ("practice","pages/1_Practice.py","📝 Guided Practice"),
            ("timed",   "pages/2_Timed.py",  "⏱️ Timed Station"),
            ("review",  "pages/3_Review.py",  "📊 Review & Analytics"),
            ("admin",   "pages/4_Admin.py",   "⚙️ Admin"),
        ]
        for key, path, label in pages:
            if key == active:
                st.markdown(f"**▸ {label}**")
            else:
                st.page_link(path, label=label)

        st.markdown("---")

        # Quick stats
        stats = get_study_stats(user_id)
        st.markdown(f"📚 **Due:** {stats['due_count']}")
        st.markdown(f"🆕 **New:** {stats['new_count']}")
        if stats["has_skill_data"]:
            st.markdown(f"⚠️ **Weakest:** {stats['weakest_skill'].title()}")
        else:
            st.markdown("⚠️ **Weakest:** _not yet assessed_")

        st.markdown("---")

        if st.button("🔀 Switch Profile", use_container_width=True):
            # Use Streamlit's logout if available
            try:
                if hasattr(st, "logout"):
                    st.logout()
            except Exception:
                pass
            for k in ("user_id", "user_name", "user_avatar"):
                st.session_state.pop(k, None)
            st.rerun()
