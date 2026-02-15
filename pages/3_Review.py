"""
Review & Analytics — Skill radar, weak areas, past attempts, due cards.
"""

import streamlit as st
import json
import plotly.graph_objects as go
from db import (
    init_db, get_user_skills, get_user_attempts, get_due_cards,
    get_new_cards, SKILL_NAMES, count_questions,
)
from srs import get_study_stats, select_next_card
from archetypes import get_archetype_names, get_archetype, ARCHETYPES
from seed_loader import load_seed_questions
from ui_shared import require_login, render_sidebar, inject_css

st.set_page_config(page_title="Review & Analytics | MMI Prep", page_icon="📊", layout="wide")

user_id, user_name = require_login()
init_db()
load_seed_questions()
inject_css()
render_sidebar("review")

# ─── Header ──────────────────────────────────────────────────────
st.markdown('<p class="main-header">Review & Analytics</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Track your progress and target your weak spots.</p>', unsafe_allow_html=True)

# ─── Quick Stats Row ─────────────────────────────────────────────
stats = get_study_stats(user_id)
skills = get_user_skills(user_id)
attempts_all = get_user_attempts(user_id, limit=1000)
has_data = stats.get("has_skill_data", False)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        '<div class="stat-card"><div class="stat-value">'
        f'{stats["due_count"]}</div><div class="stat-label">Due Cards</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        '<div class="stat-card"><div class="stat-value">'
        f'{stats["new_count"]}</div><div class="stat-label">New Cards</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    weakest = stats["weakest_skill"].title() if has_data else "—"
    st.markdown(
        '<div class="stat-card"><div class="stat-value">'
        f'{weakest}</div><div class="stat-label">Weakest Skill</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        '<div class="stat-card"><div class="stat-value">'
        f'{len(attempts_all)}</div><div class="stat-label">Total Attempts</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ─── Skill Radar Chart ──────────────────────────────────────────
st.subheader("🎯 Skill Radar")

skill_labels = [s.title() for s in SKILL_NAMES]
# Use 0 for unassessed skills so the chart renders cleanly
skill_values = [
    skills[s]["ema_score"] if skills[s]["ema_score"] is not None else 0
    for s in SKILL_NAMES
]
any_assessed = any(skills[s]["ema_score"] is not None for s in SKILL_NAMES)

# Close polygon
labels_closed = skill_labels + [skill_labels[0]]
values_closed = skill_values + [skill_values[0]]

fig = go.Figure()

if any_assessed:
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=labels_closed,
        fill='toself',
        name='Your Skills',
        line_color='#667eea',
        fillcolor='rgba(102, 126, 234, 0.3)',
    ))

# Target reference
fig.add_trace(go.Scatterpolar(
    r=[4] * len(labels_closed),
    theta=labels_closed,
    fill='toself',
    name='Target (4/5)',
    line_color='rgba(0, 200, 0, 0.3)',
    fillcolor='rgba(0, 200, 0, 0.05)',
))

fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
    showlegend=True,
    height=420,
    margin=dict(t=30, b=30),
)

st.plotly_chart(fig, use_container_width=True)

if not any_assessed:
    st.markdown(
        '<div class="empty-state"><div class="icon">📡</div>'
        '<p>No skill data yet — complete a practice session to see your radar.</p></div>',
        unsafe_allow_html=True,
    )

# ─── Weakest Skills Detail ──────────────────────────────────────
st.subheader("📉 Your 2 Weakest Skills")

if has_data:
    assessed = [s for s in SKILL_NAMES if skills[s]["ema_score"] is not None]
    sorted_skills = sorted(assessed, key=lambda s: skills[s]["ema_score"])

    for sk in sorted_skills[:2]:
        score = skills[sk]["ema_score"]
        n = skills[sk]["n_attempts"]
        col_a, col_b = st.columns([1, 3])
        with col_a:
            color = "🔴" if score < 2.5 else "🟡" if score < 3.5 else "🟢"
            st.markdown(f"### {color} {sk.title()}")
            st.markdown(f"**Score:** {score:.1f} / 5.0")
            st.markdown(f"**Attempts:** {n}")
        with col_b:
            best_arch = max(ARCHETYPES.values(), key=lambda a: a.skill_weights.get(sk, 0))
            st.markdown(f"**Best practice for {sk}:** {best_arch.name}")
            st.markdown(f"*{best_arch.goal}*")
            st.markdown(f"Key steps that build **{sk}**:")
            for step in best_arch.steps[:3]:
                st.markdown(f"- {step.prompt}")
else:
    st.markdown(
        '<div class="empty-state"><div class="icon">🧩</div>'
        '<p>Complete some practice to reveal your weakest skills.</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ─── Next Best Drill ────────────────────────────────────────────
st.subheader("🎯 Next Best Drill")

card = select_next_card(user_id)
if card:
    arch_key = card.get("archetype", "ethical_dilemma")
    arch = get_archetype(arch_key)
    st.markdown(
        f'<div class="action-card"><h4>{arch.name}</h4>'
        f'<small>Difficulty D{card.get("difficulty_base", 1)}</small></div>',
        unsafe_allow_html=True,
    )
    st.info(card.get("prompt_text", "N/A"))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Guided Practice", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Practice.py")
    with col2:
        if st.button("⏱️ Timed Station", use_container_width=True):
            st.switch_page("pages/2_Timed.py")
else:
    st.markdown(
        '<div class="empty-state"><div class="icon">🎉</div>'
        '<p>No cards to review right now — import more or wait for cards to come due.</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ─── Due Cards ───────────────────────────────────────────────────
st.subheader("📅 Cards Due Today")

due = get_due_cards(user_id, limit=20)
if due:
    for i, card in enumerate(due):
        arch_label = card.get("archetype", "?").replace("_", " ").title()
        prompt_preview = card.get("prompt_text", "N/A")[:80]
        with st.expander(f"{i + 1}. [{arch_label}] {prompt_preview}…"):
            st.markdown(f"**Full prompt:** {card.get('prompt_text', 'N/A')}")
            st.markdown(
                f"**Ease:** {card.get('ease', 2.5):.2f} · "
                f"**Interval:** {card.get('interval_days', 1)} days · "
                f"**Reps:** {card.get('repetitions', 0)}"
            )
else:
    st.success("✅ No cards due today — nice work staying on top of practice!")

st.markdown("---")

# ─── Recent Attempts ────────────────────────────────────────────
st.subheader("📜 Recent Attempts")

attempts = get_user_attempts(user_id, limit=20)
if attempts:
    for att in attempts:
        rubric = json.loads(att.get("rubric_json", "{}")) if isinstance(att.get("rubric_json"), str) else att.get("rubric_json", {})
        scores = rubric.get("scores", {})
        overall = rubric.get("overall_score_0_to_10", 0)

        mode_icon = "📝" if att["mode"] == "guided" else "⏱️"
        arch_label = att.get("archetype", "?").replace("_", " ").title()

        with st.expander(f"{mode_icon} [{arch_label}] Score: {overall}/10 — {att['created_at'][:16]}"):
            st.markdown(f"**Prompt:** {att.get('prompt_text', 'N/A')}")
            st.markdown(f"**Mode:** {att['mode'].title()} · **Difficulty:** D{att['difficulty_used']}")

            if overall:
                score_color = "🟢" if overall >= 8 else "🟡" if overall >= 5 else "🔴"
                st.markdown(f"**Overall: {score_color} {overall}/10**")

            # Quick coaching scores (0-2)
            granular = rubric.get("rubric_0_to_2_each", {})
            if granular:
                g_cols = st.columns(5)
                g_names = ["structure", "empathy", "information_gathering", "reasoning", "professionalism"]
                for gi, gn in enumerate(g_names):
                    with g_cols[gi]:
                        val = granular.get(gn, 0)
                        bar = "🟢" if val == 2 else "🟡" if val == 1 else "🔴"
                        st.caption(f"{gn.replace('_', ' ').title()}: {bar} {val}/2")

            # Detailed scores (0-5)
            if scores:
                cols = st.columns(6)
                for si, (k, v) in enumerate(scores.items()):
                    with cols[si % 6]:
                        st.metric(k.title(), f"{v}/5")

            # What worked / to improve
            worked = rubric.get("what_worked", [])
            improve = rubric.get("what_to_improve", [])
            if worked:
                st.success("**Worked:** " + ", ".join(worked))
            if improve:
                st.error("**Improve:** " + ", ".join(improve))

            micro = rubric.get("micro_upgrade", "")
            if micro:
                st.warning(f"**Quick upgrade:** {micro}")

            if rubric.get("top_3_improvements"):
                st.markdown("**Improvements:**")
                for imp in rubric["top_3_improvements"]:
                    st.markdown(f"- {imp}")

            if rubric.get("best_line_you_said"):
                st.markdown(f"**Best line:** {rubric['best_line_you_said']}")
else:
    st.markdown(
        '<div class="empty-state"><div class="icon">📝</div>'
        '<p>No attempts yet — start practicing to see your history!</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ─── Archetype Breakdown ────────────────────────────────────────
st.subheader("📂 Practice by Archetype")

arch_names = get_archetype_names()
arch_counts = {}
for att in attempts_all:
    a = att.get("archetype", "unknown")
    arch_counts[a] = arch_counts.get(a, 0) + 1

for key, name in arch_names.items():
    count = arch_counts.get(key, 0)
    pct = (count / max(len(attempts_all), 1)) * 100
    st.markdown(f"**{name}** — {count} attempt{'s' if count != 1 else ''}")
    st.progress(min(pct / 100, 1.0) if attempts_all else 0.0)

st.markdown("---")
st.caption("MMI Prep · Review & Analytics")
