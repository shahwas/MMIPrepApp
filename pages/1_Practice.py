"""
Guided Practice Page — Step-by-step MMI coaching with signpost framework.
Enhanced with dual scoring, micro-upgrades, and model answer generation.
"""

import streamlit as st
import json
from db import (
    init_db, get_all_questions, get_questions_by_archetype,
    insert_attempt, get_question_by_id,
)
from archetypes import get_archetype_names, get_archetype, ARCHETYPES
from llm import evaluate_step, generate_rubric, generate_model_answer
from srs import record_review, quality_from_scores, update_skills_from_rubric, select_next_card
from seed_loader import load_seed_questions
from models import SIGNPOST_FRAMEWORK
from ui_shared import require_login, render_sidebar, inject_css

st.set_page_config(page_title="Guided Practice | MMI Prep", page_icon="📝", layout="wide")

user_id, user_name = require_login()
init_db()
load_seed_questions()
inject_css()

# ─── Session state init ──────────────────────────────────────────
defaults = {
    "practice_started": False,
    "current_question": None,
    "current_step_idx": 0,
    "conversation": [],
    "step_feedback": [],
    "station_complete": False,
    "rubric": None,
    "difficulty_slider": 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset_practice():
    for k, v in defaults.items():
        st.session_state[k] = v


# ─── Question Selection ──────────────────────────────────────────
if not st.session_state.practice_started:
    render_sidebar(active="practice")

    st.markdown("# 📝 Guided Practice")
    st.markdown("*Step-by-step coaching with the 7-Step Signpost Framework.*")
    st.markdown("---")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Choose a Station")

        selection_mode = st.radio(
            "How would you like to pick a question?",
            ["🎯 Adaptive (best for you)", "📂 By Archetype", "🔀 Random"],
            horizontal=True,
        )

        if selection_mode == "📂 By Archetype":
            arch_names = get_archetype_names()
            selected_arch = st.selectbox(
                "Archetype",
                options=list(arch_names.keys()),
                format_func=lambda x: arch_names[x],
            )
            questions = get_questions_by_archetype(selected_arch)
            if questions:
                selected_q = st.selectbox(
                    "Question",
                    options=questions,
                    format_func=lambda q: q["prompt_text"][:120] + ("…" if len(q["prompt_text"]) > 120 else ""),
                )
            else:
                st.warning("No questions for this archetype yet.")
                selected_q = None
        else:
            selected_q = None

    with col2:
        st.subheader("Settings")
        diff_override = st.slider(
            "Difficulty Override (0 = use base)",
            min_value=0, max_value=5, value=0,
            help="0 = use the question's base difficulty. 1-5 = override.",
        )
        st.session_state.difficulty_slider = diff_override

        st.markdown("---")
        st.markdown("**The 7-Step Signpost Framework:**")
        for i, step in enumerate(SIGNPOST_FRAMEWORK):
            st.caption(f"{i+1}. {step}")

    st.markdown("---")

    if st.button("🚀 Start Station", type="primary", use_container_width=True):
        if selection_mode == "🎯 Adaptive (best for you)":
            card = select_next_card(user_id)
            if card:
                selected_q = card
            else:
                st.error("No questions available. Import some questions first.")
                st.stop()
        elif selection_mode == "🔀 Random":
            import random
            all_q = get_all_questions()
            if all_q:
                selected_q = random.choice(all_q)
            else:
                st.error("No questions available.")
                st.stop()

        if selected_q:
            qid = selected_q.get("id") or selected_q.get("question_id", "")
            full_q = get_question_by_id(qid)
            if not full_q:
                full_q = selected_q

            st.session_state.current_question = full_q
            st.session_state.practice_started = True
            st.session_state.current_step_idx = 0
            st.session_state.conversation = []
            st.session_state.step_feedback = []
            st.session_state.station_complete = False
            st.session_state.rubric = None
            st.rerun()

# ─── Active Practice Session ─────────────────────────────────────
elif st.session_state.practice_started and not st.session_state.station_complete:
    q = st.session_state.current_question
    arch = get_archetype(q["archetype"])
    steps = arch.steps
    current_idx = st.session_state.current_step_idx

    # Sidebar with progress
    with st.sidebar:
        from ui_shared import render_sidebar
        # Minimal sidebar during practice — show progress
        st.markdown(f"### 🩺 {user_name}")
        st.markdown("---")
        st.markdown("### Station Progress")
        for i, s in enumerate(steps):
            if i < current_idx:
                st.markdown(f"✅ Step {i+1}: {s.prompt[:35]}…")
            elif i == current_idx:
                st.markdown(f"▶️ **Step {i+1}: {s.prompt[:35]}…**")
            else:
                st.markdown(f"⬜ Step {i+1}: {s.prompt[:35]}…")

        pct = int((current_idx / len(steps)) * 100) if steps else 0
        st.progress(current_idx / len(steps) if steps else 0)
        st.caption(f"{current_idx}/{len(steps)} steps complete")

        st.markdown("---")
        st.markdown("### 🗺️ Signpost Framework")
        for i, sf in enumerate(SIGNPOST_FRAMEWORK):
            st.caption(f"{i+1}. {sf}")

    # Header
    st.markdown(f"## 🎯 {arch.name}")

    difficulty = st.session_state.difficulty_slider or q.get("difficulty_base", 1)
    diff_dots = "🟢" * min(difficulty, 2) + "🟡" * max(0, min(difficulty - 2, 2)) + "🔴" * max(0, difficulty - 4)
    st.caption(f"Difficulty {diff_dots} D{difficulty}")

    st.info(f"**Prompt:** {q['prompt_text']}")
    st.markdown("---")

    # Conversation history
    for entry in st.session_state.conversation:
        with st.chat_message("assistant"):
            st.markdown(f"**Step — {entry['step_prompt']}**")
        with st.chat_message("user"):
            st.markdown(entry["answer"])
        if entry.get("feedback"):
            fb = entry["feedback"]
            with st.chat_message("assistant"):
                if fb.get("step_complete"):
                    st.success("✅ Good! Moving to next step.")
                if fb.get("missing_points"):
                    st.markdown("**Consider adding:** " + "; ".join(fb["missing_points"]))
                if fb.get("one_best_nudge"):
                    st.markdown(f"💡 **Nudge:** {fb['one_best_nudge']}")
                if fb.get("signpost_step_hint"):
                    st.caption(f"🗺️ Signpost hint: {fb['signpost_step_hint']}")

    # Current step
    if current_idx < len(steps):
        current_step = steps[current_idx]
        with st.chat_message("assistant"):
            st.markdown(f"### Step {current_idx + 1} of {len(steps)}")
            st.markdown(f"**{current_step.prompt}**")

        col_a, col_b = st.columns([3, 1])
        with col_b:
            if st.button("💬 Example line", key=f"marker_{current_idx}"):
                import random
                marker = random.choice(arch.human_markers)
                st.info(f'Try: *"{marker}"*')

        user_answer = st.text_area(
            "Your answer:",
            key=f"step_answer_{current_idx}",
            height=150,
            placeholder=f"Focus on: {current_step.coach_focus}",
        )

        col_sub, col_skip, col_quit = st.columns([2, 1, 1])
        with col_sub:
            if st.button("Submit Step ➡️", type="primary", key=f"submit_{current_idx}", use_container_width=True):
                if not user_answer.strip():
                    st.warning("Please write something before submitting.")
                else:
                    with st.spinner("Evaluating your response…"):
                        feedback = evaluate_step(
                            archetype_key=q["archetype"],
                            step_id=current_step.id,
                            prompt_text=q["prompt_text"],
                            user_answer=user_answer,
                            conversation_so_far=st.session_state.conversation,
                        )

                    st.session_state.conversation.append({
                        "step": current_step.id,
                        "step_prompt": current_step.prompt,
                        "answer": user_answer,
                        "feedback": feedback,
                    })
                    st.session_state.step_feedback.append(feedback)

                    if feedback.get("step_complete", True) or feedback.get("next_step_id") != current_step.id:
                        st.session_state.current_step_idx += 1
                        if st.session_state.current_step_idx >= len(steps):
                            st.session_state.station_complete = True

                    st.rerun()
        with col_skip:
            if st.button("⏭️ Skip", key=f"skip_{current_idx}", use_container_width=True):
                st.session_state.conversation.append({
                    "step": current_step.id,
                    "step_prompt": current_step.prompt,
                    "answer": "(skipped)",
                    "feedback": None,
                })
                st.session_state.current_step_idx += 1
                if st.session_state.current_step_idx >= len(steps):
                    st.session_state.station_complete = True
                st.rerun()
        with col_quit:
            if st.button("🛑 End", key="end_early", use_container_width=True):
                st.session_state.station_complete = True
                st.rerun()

# ─── Station Complete — Enhanced Rubric ──────────────────────────
elif st.session_state.station_complete:
    q = st.session_state.current_question
    arch = get_archetype(q["archetype"])
    render_sidebar(active="practice")

    st.markdown("## 🏁 Station Complete!")
    st.markdown("---")

    # Build full transcript
    full_transcript = "\n\n".join(
        f"**Step ({e['step']})**: {e['step_prompt']}\n**My answer**: {e['answer']}"
        for e in st.session_state.conversation
        if e["answer"] != "(skipped)"
    )

    # Generate rubric
    if st.session_state.rubric is None:
        with st.spinner("🔍 Generating your detailed rubric…"):
            rubric = generate_rubric(
                archetype_key=q["archetype"],
                prompt_text=q["prompt_text"],
                full_transcript=full_transcript,
                mode="guided",
            )
            st.session_state.rubric = rubric

            scores = rubric.get("scores", {})
            difficulty = st.session_state.difficulty_slider or q.get("difficulty_base", 1)

            insert_attempt(
                user_id=user_id,
                question_id=q["id"],
                mode="guided",
                difficulty_used=difficulty,
                transcript_text=full_transcript,
                step_json=st.session_state.conversation,
                rubric_json=rubric,
            )

            quality = quality_from_scores(scores)
            record_review(user_id, q["id"], quality)
            update_skills_from_rubric(user_id, scores)

    rubric = st.session_state.rubric
    scores = rubric.get("scores", {})
    granular = rubric.get("rubric_0_to_2_each", {})
    overall = rubric.get("overall_score_0_to_10", 0)

    # ── Overall Score ────────────────────────────────────────────
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

    # ── Quick Coaching (0-2) ─────────────────────────────────────
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

    # ── Detailed Skills (0-5) ────────────────────────────────────
    st.subheader("📊 Detailed Skill Scores (0–5 each)")
    score_cols = st.columns(6)
    score_names = ["structure", "empathy", "perspective", "reasoning", "actionability", "clarity"]
    score_emojis = ["🏗️", "❤️", "👁️", "🧠", "⚡", "💬"]
    for i, name in enumerate(score_names):
        with score_cols[i]:
            val = scores.get(name, 0)
            st.metric(f"{score_emojis[i]} {name.title()}", f"{val}/5")

    st.markdown("---")

    # ── Micro Upgrade ────────────────────────────────────────────
    micro = rubric.get("micro_upgrade", "")
    if micro:
        st.subheader("⚡ Quick Upgrade")
        st.warning(micro)

    # ── Top 3 Improvements ───────────────────────────────────────
    st.subheader("🎯 Top 3 Improvements")
    for imp in rubric.get("top_3_improvements", []):
        st.markdown(f"- {imp}")

    # ── Best Line ────────────────────────────────────────────────
    best = rubric.get("best_line_you_said", "")
    if best:
        st.subheader("⭐ Best Line You Said")
        st.success(best)

    st.markdown("---")

    # ── Model Rewrites ───────────────────────────────────────────
    st.subheader("✍️ Model Rewrites")
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
        st.subheader("🤖 AI Model Answer (90s)")
        st.markdown(model_ans)

    st.markdown("---")

    # ── Signpost Framework ───────────────────────────────────────
    with st.expander("🗺️ Recommended Signpost Framework"):
        framework = rubric.get("recommended_signpost_framework", SIGNPOST_FRAMEWORK)
        for i, step in enumerate(framework):
            st.markdown(f"**{i+1}.** {step}")

    # ── Follow-ups ───────────────────────────────────────────────
    with st.expander("❓ Interviewer Follow-ups"):
        for fu in rubric.get("interviewer_followups", []):
            st.markdown(f"- {fu}")

    # ── Transcript ───────────────────────────────────────────────
    with st.expander("📜 Full Transcript"):
        for entry in st.session_state.conversation:
            st.markdown(f"**Step ({entry['step']}):** {entry['step_prompt']}")
            st.markdown(f"> {entry['answer']}")
            if entry.get("feedback") and entry["feedback"].get("one_best_nudge"):
                st.caption(f"💡 Nudge: {entry['feedback']['one_best_nudge']}")
            st.markdown("---")

    st.markdown("---")
    col_next, col_home = st.columns(2)
    with col_next:
        if st.button("🔄 Practice Another Station", type="primary", use_container_width=True):
            reset_practice()
            st.rerun()
    with col_home:
        if st.button("🏠 Back to Home", use_container_width=True):
            reset_practice()
            st.switch_page("app.py")
