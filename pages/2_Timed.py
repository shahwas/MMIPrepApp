"""
Timed Station Page — Full answer under time pressure.
2 min read + 6-8 min respond, like a real MMI circuit.
"""

import streamlit as st
import time
import random
from db import init_db, get_all_questions, get_questions_by_archetype, insert_attempt, get_question_by_id
from archetypes import get_archetype_names, get_archetype
from llm import generate_rubric, generate_followups, generate_model_answer
from srs import record_review, quality_from_scores, update_skills_from_rubric, select_next_card
from seed_loader import load_seed_questions
from models import SIGNPOST_FRAMEWORK
from ui_shared import require_login, render_sidebar, inject_css

st.set_page_config(page_title="Timed Station | MMI Prep", page_icon="⏱️", layout="wide")

user_id, user_name = require_login()
init_db()
load_seed_questions()
inject_css()

# ─── Session state defaults ──────────────────────────────────────
defaults = {
    "timed_phase": "setup",
    "timed_question": None,
    "timed_start_time": None,
    "read_time_sec": 120,
    "answer_time_sec": 480,
    "timed_answer": "",
    "timed_followup_answers": {},
    "timed_followups": [],
    "timed_rubric": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset_timed():
    for k, v in defaults.items():
        st.session_state[k] = v


# ─── SETUP PHASE ─────────────────────────────────────────────────
if st.session_state.timed_phase == "setup":
    render_sidebar(active="timed")

    st.markdown("# ⏱️ Timed Station")
    st.markdown("*Full answer under time pressure — just like a real MMI circuit.*")
    st.markdown("---")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Station Settings")

        selection = st.radio(
            "Question Selection",
            ["🎯 Adaptive", "📂 By Archetype", "🔀 Random"],
            horizontal=True,
        )

        selected_q = None
        if selection == "📂 By Archetype":
            arch_names = get_archetype_names()
            arch_key = st.selectbox("Archetype", list(arch_names.keys()), format_func=lambda x: arch_names[x])
            questions = get_questions_by_archetype(arch_key)
            if questions:
                selected_q = st.selectbox("Question", questions, format_func=lambda q: q["prompt_text"][:120] + "…")

    with col2:
        st.subheader("Timer Settings")
        read_time = st.slider("Reading time (seconds)", 30, 300, 120, step=30)
        answer_time = st.slider("Answer time (seconds)", 120, 600, 480, step=60)
        st.session_state.read_time_sec = read_time
        st.session_state.answer_time_sec = answer_time

        st.markdown(f"""
        **Your circuit:**
        - 📖 Read: {read_time // 60}m {read_time % 60}s
        - 🎤 Answer: {answer_time // 60}m {answer_time % 60}s
        - ❓ Follow-ups: untimed
        """)

    st.markdown("---")

    if st.button("🚀 Begin Station", type="primary", use_container_width=True):
        if selection == "🎯 Adaptive":
            card = select_next_card(user_id)
            selected_q = card if card else None
        elif selection == "🔀 Random":
            all_q = get_all_questions()
            selected_q = random.choice(all_q) if all_q else None

        if selected_q:
            st.session_state.timed_question = selected_q
            st.session_state.timed_phase = "reading"
            st.session_state.timed_start_time = time.time()
            st.rerun()
        else:
            st.error("No questions available.")

# ─── READING PHASE ───────────────────────────────────────────────
elif st.session_state.timed_phase == "reading":
    q = st.session_state.timed_question
    arch = get_archetype(q["archetype"])
    elapsed = time.time() - st.session_state.timed_start_time
    remaining = max(0, st.session_state.read_time_sec - elapsed)

    with st.sidebar:
        st.markdown(f"### 🩺 {user_name}")
        st.markdown("---")
        st.markdown("### ⏱️ Reading Phase")
        st.markdown(f"**{int(remaining // 60)}:{int(remaining % 60):02d}** remaining")

    st.markdown(f"### 📖 Reading Time — {arch.name}")
    st.markdown(f"## ⏱️ {int(remaining // 60)}:{int(remaining % 60):02d}")
    st.progress(min(1.0, elapsed / st.session_state.read_time_sec))

    st.markdown("---")
    st.info(q["prompt_text"])

    st.markdown("---")
    st.markdown("**While reading, think about:**")
    for i, sf in enumerate(SIGNPOST_FRAMEWORK[:4]):
        st.caption(f"{i+1}. {sf}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ I'm ready — Start answering", type="primary", use_container_width=True):
            st.session_state.timed_phase = "answering"
            st.session_state.timed_start_time = time.time()
            st.rerun()
    with col2:
        if remaining <= 0:
            st.warning("⏰ Reading time is up!")
            st.session_state.timed_phase = "answering"
            st.session_state.timed_start_time = time.time()
            st.rerun()
        else:
            if st.button("🔄 Refresh timer"):
                st.rerun()

# ─── ANSWERING PHASE ────────────────────────────────────────────
elif st.session_state.timed_phase == "answering":
    q = st.session_state.timed_question
    arch = get_archetype(q["archetype"])
    elapsed = time.time() - st.session_state.timed_start_time
    remaining = max(0, st.session_state.answer_time_sec - elapsed)

    with st.sidebar:
        st.markdown(f"### 🩺 {user_name}")
        st.markdown("---")
        st.markdown("### 🎤 Answering Phase")
        color = "🟢" if remaining > 120 else "🟡" if remaining > 30 else "🔴"
        st.markdown(f"{color} **{int(remaining // 60)}:{int(remaining % 60):02d}** remaining")

    st.markdown(f"### 🎤 Answer Time — {arch.name}")

    if remaining > 0:
        st.markdown(f"## ⏱️ {int(remaining // 60)}:{int(remaining % 60):02d}")
        st.progress(min(1.0, elapsed / st.session_state.answer_time_sec))
    else:
        st.error("⏰ **Time's up!** Submit your answer now.")

    st.caption(f"**Prompt:** {q['prompt_text']}")
    st.markdown("---")

    with st.expander("📋 Step guide (try to cover these)"):
        for i, s in enumerate(arch.steps):
            st.markdown(f"{i+1}. {s.prompt}")

    answer = st.text_area(
        "Your complete answer:",
        height=350,
        key="timed_answer_input",
        placeholder="Structure your answer using the step ladder…",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("📤 Submit Answer", type="primary", use_container_width=True):
            if not answer.strip():
                st.warning("Write something before submitting!")
            else:
                st.session_state.timed_answer = answer
                st.session_state.timed_phase = "followup"
                st.rerun()
    with col2:
        if st.button("🛑 End Station", use_container_width=True):
            st.session_state.timed_answer = answer or "(no answer)"
            st.session_state.timed_phase = "followup"
            st.rerun()

# ─── FOLLOW-UP PHASE ────────────────────────────────────────────
elif st.session_state.timed_phase == "followup":
    q = st.session_state.timed_question
    arch = get_archetype(q["archetype"])
    render_sidebar(active="timed")

    st.markdown("### ❓ Interviewer Follow-ups")
    st.markdown("*A real MMI interviewer would probe deeper. Try answering these.*")
    st.markdown("---")

    if not st.session_state.timed_followups:
        with st.spinner("Generating follow-up questions…"):
            followups = generate_followups(
                archetype_key=q["archetype"],
                prompt_text=q["prompt_text"],
                user_answer=st.session_state.timed_answer,
            )
            st.session_state.timed_followups = followups

    for i, fu in enumerate(st.session_state.timed_followups):
        st.markdown(f"**Follow-up {i+1}:** {fu}")
        fu_answer = st.text_area(
            f"Your answer to follow-up {i+1}:",
            key=f"followup_answer_{i}",
            height=100,
        )
        st.session_state.timed_followup_answers[i] = fu_answer

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Get My Results", type="primary", use_container_width=True):
            st.session_state.timed_phase = "results"
            st.rerun()
    with col2:
        if st.button("⏭️ Skip follow-ups", use_container_width=True):
            st.session_state.timed_phase = "results"
            st.rerun()

# ─── RESULTS PHASE ──────────────────────────────────────────────
elif st.session_state.timed_phase == "results":
    q = st.session_state.timed_question
    arch = get_archetype(q["archetype"])
    render_sidebar(active="timed")

    st.markdown("## 🏁 Station Results")
    st.markdown("---")

    full_text = f"Main answer:\n{st.session_state.timed_answer}"
    for i, fu in enumerate(st.session_state.timed_followups):
        fu_ans = st.session_state.timed_followup_answers.get(i, "")
        if fu_ans.strip():
            full_text += f"\n\nFollow-up: {fu}\nAnswer: {fu_ans}"

    if st.session_state.timed_rubric is None:
        with st.spinner("🔍 Generating detailed rubric…"):
            rubric = generate_rubric(
                archetype_key=q["archetype"],
                prompt_text=q["prompt_text"],
                full_transcript=full_text,
                mode="timed",
            )
            st.session_state.timed_rubric = rubric

            scores = rubric.get("scores", {})
            insert_attempt(
                user_id=user_id,
                question_id=q["id"],
                mode="timed",
                difficulty_used=q.get("difficulty_base", 1),
                transcript_text=full_text,
                step_json={"followups": st.session_state.timed_followup_answers},
                rubric_json=rubric,
            )
            quality = quality_from_scores(scores)
            record_review(user_id, q["id"], quality)
            update_skills_from_rubric(user_id, scores)

    rubric = st.session_state.timed_rubric
    scores = rubric.get("scores", {})
    granular = rubric.get("rubric_0_to_2_each", {})
    overall = rubric.get("overall_score_0_to_10", 0)

    # Overall Score
    score_color = "🟢" if overall >= 8 else "🟡" if overall >= 5 else "🔴"
    st.markdown(f"""
    <div class="stat-card" style="max-width:220px;">
        <div class="stat-value">{score_color} {overall}/10</div>
        <div class="stat-label">Overall Score</div>
    </div>
    """, unsafe_allow_html=True)

    col_w, col_i = st.columns(2)
    with col_w:
        worked = rubric.get("what_worked", [])
        if worked:
            st.success("**What worked:** " + ", ".join(worked))
    with col_i:
        improve = rubric.get("what_to_improve", [])
        if improve:
            st.error("**What to improve:** " + ", ".join(improve))

    st.markdown("---")

    # Quick Coaching (0-2)
    st.subheader("⚡ Quick Coaching Score (0–2 each)")
    g_cols = st.columns(5)
    g_names = ["structure", "empathy", "information_gathering", "reasoning", "professionalism"]
    g_emojis = ["🏗️", "❤️", "🔍", "🧠", "🤝"]
    for i, name in enumerate(g_names):
        with g_cols[i]:
            val = granular.get(name, 0)
            bar = "🟢" if val == 2 else "🟡" if val == 1 else "🔴"
            st.metric(f"{g_emojis[i]} {name.replace('_', ' ').title()}", f"{bar} {val}/2")

    st.markdown("---")

    # Detailed Skills (0-5)
    st.subheader("📊 Detailed Skill Scores (0–5 each)")
    score_cols = st.columns(6)
    score_names = ["structure", "empathy", "perspective", "reasoning", "actionability", "clarity"]
    score_emojis = ["🏗️", "❤️", "👁️", "🧠", "⚡", "💬"]
    for i, name in enumerate(score_names):
        with score_cols[i]:
            val = scores.get(name, 0)
            st.metric(f"{score_emojis[i]} {name.title()}", f"{val}/5")

    st.markdown("---")

    micro = rubric.get("micro_upgrade", "")
    if micro:
        st.subheader("⚡ Quick Upgrade")
        st.warning(micro)

    st.subheader("🎯 Top 3 Improvements")
    for imp in rubric.get("top_3_improvements", []):
        st.markdown(f"- {imp}")

    best = rubric.get("best_line_you_said", "")
    if best:
        st.subheader("⭐ Best Line You Said")
        st.success(best)

    st.markdown("---")

    # Model rewrites
    st.subheader("✍️ Model Answers")
    col_30, col_90 = st.columns(2)
    with col_30:
        st.markdown("**30-Second Version:**")
        st.info(rubric.get("rewrite_30s", "N/A"))
    with col_90:
        st.markdown("**90-Second Version:**")
        st.info(rubric.get("rewrite_90s", "N/A"))

    if st.button("🤖 Generate Full Model Answer"):
        with st.spinner("Generating model answer…"):
            model_ans = generate_model_answer(q["prompt_text"], "90s")
        st.subheader("🤖 AI Model Answer")
        st.markdown(model_ans)

    st.markdown("---")

    with st.expander("🗺️ Recommended Signpost Framework"):
        framework = rubric.get("recommended_signpost_framework", SIGNPOST_FRAMEWORK)
        for i, step in enumerate(framework):
            st.markdown(f"**{i+1}.** {step}")

    with st.expander("❓ Additional Follow-ups"):
        for fu in rubric.get("interviewer_followups", []):
            st.markdown(f"- {fu}")

    with st.expander("📜 Your Full Answer"):
        st.markdown(st.session_state.timed_answer)
        for i, fu in enumerate(st.session_state.timed_followups):
            fu_ans = st.session_state.timed_followup_answers.get(i, "")
            if fu_ans.strip():
                st.markdown(f"**Follow-up:** {fu}")
                st.markdown(f"> {fu_ans}")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try Another Station", type="primary", use_container_width=True):
            reset_timed()
            st.rerun()
    with col2:
        if st.button("🏠 Back to Home", use_container_width=True):
            reset_timed()
            st.switch_page("app.py")
