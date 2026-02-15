"""
MMI Prep App — Main entry point / Dashboard.
Practice MMI like Anki, with a live AI tutor.
"""

import streamlit as st
from db import init_db, count_questions, get_user_skills, SKILL_NAMES
from seed_loader import load_seed_questions
from srs import get_study_stats
from archetypes import get_archetype_names, get_archetype
from ui_shared import require_login, render_sidebar, inject_css

# ─── Page config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="MMI Prep",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Auth gate ───────────────────────────────────────────────────
user_id, user_name = require_login()

# ─── Init ────────────────────────────────────────────────────────
init_db()
load_seed_questions()
inject_css()
render_sidebar(active="home")

# ─── Main content ────────────────────────────────────────────────
stats = get_study_stats(user_id)
skills = get_user_skills(user_id)
has_data = stats["has_skill_data"]

st.markdown(f'<p class="main-header">Welcome back, {user_name} 👋</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Practice MMI like Anki — with a live AI tutor that scaffolds your thinking step by step.</p>', unsafe_allow_html=True)

# ─── Quick Stats ─────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-value">{count_questions()}</div>
        <div class="stat-label">Questions in Bank</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-value">{stats['due_count']}</div>
        <div class="stat-label">Cards Due Today</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-value">{stats['new_count']}</div>
        <div class="stat-label">New Cards</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    if has_data:
        weakest = stats["weakest_skill"]
        score = skills.get(weakest, {}).get("ema_score")
        val_str = f"{score:.1f}/5" if score is not None else "?"
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{val_str}</div>
            <div class="stat-label">Weakest: {weakest.title()}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">—</div>
            <div class="stat-label">Complete a station to see stats</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")

# ─── Skill Profile ───────────────────────────────────────────────
st.subheader("📊 Your Skill Profile")

colors = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe"]
skill_cols = st.columns(len(SKILL_NAMES))

for i, skill in enumerate(SKILL_NAMES):
    with skill_cols[i]:
        s = skills[skill]
        score = s["ema_score"]
        n = s["n_attempts"]
        color = colors[i % len(colors)]

        st.markdown(f"**{skill.title()}**")
        if score is not None and n > 0:
            pct = (score / 5.0) * 100
            st.markdown(f"""
            <div class="skill-bar-outer">
                <div class="skill-bar-fill" style="width: {pct}%; background: {color};"></div>
            </div>
            <small>{score:.1f} / 5.0 &nbsp;·&nbsp; {n} attempt{'s' if n != 1 else ''}</small>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="skill-bar-outer">
                <div class="skill-bar-fill" style="width: 0%; background: #ccc;"></div>
            </div>
            <span class="skill-unknown">Not yet assessed</span>
            """, unsafe_allow_html=True)

st.markdown("---")

# ─── Quick Start ─────────────────────────────────────────────────
st.subheader("🚀 Quick Start")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("""
    <div class="action-card">
        <h4>📝 Guided Practice</h4>
        <small>Step-by-step coaching — the app prompts you one step at a time, like a great tutor.</small>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Start Guided Practice", use_container_width=True, type="primary"):
        st.switch_page("pages/1_Practice.py")

with col_b:
    st.markdown("""
    <div class="action-card">
        <h4>⏱️ Timed Station</h4>
        <small>Full answer under time pressure · 2 min read + 6–8 min respond. Just like the real thing.</small>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Start Timed Station", use_container_width=True):
        st.switch_page("pages/2_Timed.py")

with col_c:
    st.markdown("""
    <div class="action-card">
        <h4>📊 Review Analytics</h4>
        <small>See your skill radar, weakest areas, and next best drill.</small>
    </div>
    """, unsafe_allow_html=True)
    if st.button("View Analytics", use_container_width=True):
        st.switch_page("pages/3_Review.py")

st.markdown("---")

# ─── Station Archetypes Overview ─────────────────────────────────
st.subheader("🗂️ Station Archetypes")

arch_names = get_archetype_names()
cols = st.columns(2)
for i, (key, name) in enumerate(arch_names.items()):
    arch = get_archetype(key)
    with cols[i % 2]:
        with st.expander(f"**{name}**"):
            st.markdown(f"**Goal:** {arch.goal}")
            st.markdown("**Step Ladder:**")
            for s in arch.steps:
                st.markdown(f"- {s.prompt}")
            st.markdown("**Human Markers:**")
            for m in arch.human_markers[:3]:
                st.markdown(f'- *"{m}"*')

st.markdown("---")
st.caption("MMI Prep · AI-Powered Interview Practice · Built with Streamlit + OpenAI")
