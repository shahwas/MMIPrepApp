"""
Admin — Import PDFs/text, tag questions, generate variants, manage data.
"""

import streamlit as st
import json
import os
from db import (
    init_db, get_all_questions, insert_question, delete_question,
    count_questions, get_conn, get_all_users, delete_user,
    get_user_attempts, SKILL_NAMES,
)
from archetypes import get_archetype_names
from seed_loader import load_seed_questions
from llm import extract_question_from_chunk, mutate_difficulty, generate_question
from model_config import get_all_models, MODEL
from knowledge import KNOWLEDGE_SUMMARY
from ui_shared import require_login, render_sidebar, inject_css

st.set_page_config(page_title="Admin | MMI Prep", page_icon="⚙️", layout="wide")

user_id, user_name = require_login()
init_db()
load_seed_questions()
inject_css()
render_sidebar("admin")

# ─── Header ──────────────────────────────────────────────────────
st.markdown('<p class="main-header">Admin Panel</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Manage questions, import content, and maintain your data.</p>', unsafe_allow_html=True)

# ─── Tabs ────────────────────────────────────────────────────────
tab_bank, tab_import, tab_generate, tab_mutate, tab_manual, tab_model, tab_data = st.tabs([
    "📚 Question Bank", "📄 Import PDF/Text", "🤖 AI Generate",
    "🔄 Difficulty Mutator", "✍️ Add Manual", "🧠 Model & Knowledge", "💾 Data Management",
])

# ─── Question Bank ──────────────────────────────────────────────
with tab_bank:
    st.subheader(f"Question Bank ({count_questions()} questions)")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        arch_filter = st.selectbox(
            "Archetype",
            ["All"] + list(get_archetype_names().keys()),
            format_func=lambda x: "All Archetypes" if x == "All" else get_archetype_names().get(x, x),
        )
    with col_f2:
        source_filter = st.selectbox(
            "Source",
            ["All", "seed", "training-data", "imported", "ai-generated", "mutated", "manual"],
        )

    questions = get_all_questions()
    if arch_filter != "All":
        questions = [q for q in questions if q["archetype"] == arch_filter]
    if source_filter != "All":
        questions = [q for q in questions if q["source_pack"] == source_filter]

    st.caption(f"Showing {len(questions)} questions")

    for q in questions:
        tags = json.loads(q["tags"]) if isinstance(q["tags"], str) else q["tags"]
        with st.expander(
            f"[{q['archetype'].replace('_', ' ').title()}] D{q['difficulty_base']} — "
            f"{q['prompt_text'][:80]}…"
        ):
            st.markdown(f"**Full Prompt:** {q['prompt_text']}")
            st.markdown(
                f"**Archetype:** {q['archetype']} · **Difficulty:** D{q['difficulty_base']} · "
                f"**Source:** {q['source_pack']}"
            )
            st.markdown(f"**Tags:** {', '.join(tags) if tags else 'None'}")
            st.caption(f"ID: {q['id']}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 Mutate", key=f"mut_{q['id']}"):
                    st.session_state[f"mutating_{q['id']}"] = True
            with c2:
                if st.button("🗑️ Delete", key=f"del_{q['id']}"):
                    delete_question(q["id"])
                    st.success("Deleted!")
                    st.rerun()

            if st.session_state.get(f"mutating_{q['id']}"):
                target_d = st.slider(
                    f"Target difficulty for '{q['prompt_text'][:40]}…'",
                    1, 5, 3, key=f"d_{q['id']}",
                )
                if st.button(f"Generate D{target_d} variant", key=f"gen_{q['id']}"):
                    with st.spinner("Mutating…"):
                        result = mutate_difficulty(q["prompt_text"], q["difficulty_base"], target_d)
                    st.info(f"**Mutated (D{target_d}):** {result['mutated_prompt']}")
                    st.caption(f"Notes: {result['mutation_notes']}")
                    if st.button(f"✅ Save variant", key=f"save_{q['id']}"):
                        insert_question(q["archetype"], target_d, result["mutated_prompt"], tags, "mutated")
                        st.success("Saved!")
                        st.session_state[f"mutating_{q['id']}"] = False
                        st.rerun()

# ─── Import PDF/Text ─────────────────────────────────────────────
with tab_import:
    st.subheader("Import Questions from PDF or Text")
    st.markdown(
        "Upload a PDF or paste text with MMI practice questions. "
        "The AI will extract and classify each one automatically."
    )

    import_mode = st.radio("Source", ["📄 Upload PDF", "📝 Paste Text"], horizontal=True)
    raw_text = ""

    if import_mode == "📄 Upload PDF":
        uploaded = st.file_uploader("Upload PDF", type=["pdf"])
        if uploaded:
            try:
                import pdfplumber
                with pdfplumber.open(uploaded) as pdf:
                    raw_text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
            except ImportError:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(uploaded)
                    raw_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception as e:
                    st.error(f"Error reading PDF: {e}")
            if raw_text:
                st.success(f"Extracted {len(raw_text):,} characters from PDF.")
    else:
        raw_text = st.text_area(
            "Paste questions (one per paragraph or numbered):",
            height=300,
            placeholder="1. Is it ethical for physicians to strike?\n\n2. A patient refuses treatment…",
        )

    if raw_text and st.button("🔍 Extract Questions", type="primary"):
        import re
        chunks = re.split(r'\n\s*\n|\n(?=\d+[\.\)])', raw_text)
        chunks = [c.strip() for c in chunks if len(c.strip()) > 20]
        st.markdown(f"Found **{len(chunks)}** candidate chunks.")

        extracted = []
        progress = st.progress(0)
        for i, chunk in enumerate(chunks):
            progress.progress((i + 1) / len(chunks))
            try:
                result = extract_question_from_chunk(chunk)
                if result.get("is_question"):
                    result["original_chunk"] = chunk
                    extracted.append(result)
            except Exception as e:
                st.warning(f"Error on chunk {i + 1}: {e}")

        st.session_state["extracted_questions"] = extracted
        st.success(f"Extracted **{len(extracted)}** questions.")

    if "extracted_questions" in st.session_state and st.session_state["extracted_questions"]:
        st.markdown("### Review & Approve")
        for i, eq in enumerate(st.session_state["extracted_questions"]):
            with st.expander(f"Q{i + 1}: [{eq['archetype_guess']}] {eq['clean_prompt_text'][:80]}…"):
                st.markdown(f"**Clean prompt:** {eq['clean_prompt_text']}")
                st.markdown(f"**Archetype guess:** {eq['archetype_guess']}")
                st.markdown(f"**Tags:** {', '.join(eq['tags'])}")

                ca, cb, cc = st.columns(3)
                with ca:
                    arch_override = st.selectbox(
                        "Archetype",
                        list(get_archetype_names().keys()),
                        index=(
                            list(get_archetype_names().keys()).index(eq["archetype_guess"])
                            if eq["archetype_guess"] in get_archetype_names() else 0
                        ),
                        key=f"arch_{i}",
                    )
                with cb:
                    diff = st.slider("Difficulty", 1, 5, 2, key=f"diff_{i}")
                with cc:
                    if st.button(f"✅ Approve Q{i + 1}", key=f"approve_{i}"):
                        insert_question(arch_override, diff, eq["clean_prompt_text"], eq["tags"], "imported")
                        st.success(f"Added Q{i + 1}!")

        if st.button("✅ Approve All", type="primary"):
            count = 0
            for eq in st.session_state["extracted_questions"]:
                arch = eq["archetype_guess"] if eq["archetype_guess"] in get_archetype_names() else "ethical_dilemma"
                insert_question(arch, 2, eq["clean_prompt_text"], eq["tags"], "imported")
                count += 1
            st.success(f"Approved {count} questions!")
            del st.session_state["extracted_questions"]
            st.rerun()

# ─── AI Generate ─────────────────────────────────────────────────
with tab_generate:
    st.subheader("🤖 AI Question Generator")
    st.markdown("Generate fresh MMI questions using AI, based on real MMI patterns.")

    cg1, cg2 = st.columns(2)
    with cg1:
        gen_archetype = st.selectbox(
            "Archetype",
            list(get_archetype_names().keys()),
            format_func=lambda x: get_archetype_names()[x],
            key="gen_arch",
        )
    with cg2:
        gen_difficulty = st.slider("Difficulty", 1, 5, 3, key="gen_diff")

    gen_themes = st.text_input(
        "Themes (optional):",
        placeholder="e.g., patient autonomy, cultural sensitivity, end-of-life care",
    )
    num_questions = st.slider("Number to generate", 1, 5, 1, key="gen_count")

    if st.button("🤖 Generate Questions", type="primary"):
        generated = []
        progress = st.progress(0)
        for i in range(num_questions):
            progress.progress((i + 1) / num_questions)
            with st.spinner(f"Generating question {i + 1}…"):
                try:
                    result = generate_question(gen_archetype, gen_difficulty, gen_themes)
                    generated.append(result)
                except Exception as e:
                    st.warning(f"Error generating question {i + 1}: {e}")
        st.session_state["generated_questions"] = generated
        st.success(f"Generated {len(generated)} questions!")

    if "generated_questions" in st.session_state and st.session_state["generated_questions"]:
        st.markdown("### Review & Save")
        for i, gq in enumerate(st.session_state["generated_questions"]):
            with st.expander(f"Q{i + 1}: {gq['prompt_text'][:80]}…"):
                st.markdown(f"**Prompt:** {gq['prompt_text']}")
                st.markdown(f"**Themes:** {', '.join(gq.get('themes', []))}")
                if st.button(f"💾 Save Q{i + 1}", key=f"save_gen_{i}"):
                    insert_question(
                        gen_archetype, gen_difficulty, gq["prompt_text"],
                        gq.get("themes", []), "ai-generated",
                    )
                    st.success(f"Saved Q{i + 1}!")

        if st.button("💾 Save All Generated", type="primary"):
            count = 0
            for gq in st.session_state["generated_questions"]:
                insert_question(
                    gen_archetype, gen_difficulty, gq["prompt_text"],
                    gq.get("themes", []), "ai-generated",
                )
                count += 1
            st.success(f"Saved {count} questions!")
            del st.session_state["generated_questions"]
            st.rerun()

# ─── Difficulty Mutator ──────────────────────────────────────────
with tab_mutate:
    st.subheader("🔄 Difficulty Mutator")
    st.markdown("Generate harder or easier variants of existing questions.")

    questions_mut = get_all_questions()
    if questions_mut:
        selected = st.selectbox(
            "Select a question to mutate:",
            questions_mut,
            format_func=lambda q: f"[D{q['difficulty_base']}] {q['prompt_text'][:100]}…",
        )
        if selected:
            st.info(f"**Current (D{selected['difficulty_base']}):** {selected['prompt_text']}")
            target = st.slider("Target difficulty", 1, 5, min(5, selected["difficulty_base"] + 1))
            if st.button("🔄 Generate Variant", type="primary"):
                with st.spinner("Mutating…"):
                    result = mutate_difficulty(selected["prompt_text"], selected["difficulty_base"], target)
                st.success(f"**D{target} Variant:** {result['mutated_prompt']}")
                st.caption(f"Mutation notes: {result['mutation_notes']}")
                if st.button("💾 Save This Variant"):
                    tags = json.loads(selected["tags"]) if isinstance(selected["tags"], str) else selected["tags"]
                    insert_question(selected["archetype"], target, result["mutated_prompt"], tags, "mutated")
                    st.success("Saved to question bank!")
                    st.rerun()
    else:
        st.markdown(
            '<div class="empty-state"><div class="icon">📦</div>'
            '<p>No questions in the bank yet.</p></div>',
            unsafe_allow_html=True,
        )

# ─── Manual Add ──────────────────────────────────────────────────
with tab_manual:
    st.subheader("✍️ Add Question Manually")

    with st.form("add_question_form"):
        prompt = st.text_area("Question prompt:", height=100)
        cm1, cm2 = st.columns(2)
        with cm1:
            archetype = st.selectbox(
                "Archetype",
                list(get_archetype_names().keys()),
                format_func=lambda x: get_archetype_names()[x],
            )
        with cm2:
            difficulty = st.slider("Difficulty", 1, 5, 2)
        tags_str = st.text_input("Tags (comma-separated):", placeholder="ethics, autonomy, communication")
        submitted = st.form_submit_button("Add Question", type="primary")
        if submitted:
            if prompt.strip():
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                insert_question(archetype, difficulty, prompt.strip(), tags, "manual")
                st.success("Question added!")
                st.rerun()
            else:
                st.warning("Please enter a prompt.")

# ─── Model & Knowledge ──────────────────────────────────────────
with tab_model:
    st.subheader("🧠 Model & Knowledge Bank")

    st.markdown(f"**Model:** `{MODEL}` (used for everything)")
    st.markdown(f"**Knowledge:** {KNOWLEDGE_SUMMARY}")

    st.markdown("---")
    st.markdown("""
**How it works:** All training data is loaded as few-shot examples at runtime.
No fine-tuning required — the model receives all examples as in-context knowledge.

| Task | Examples injected |
|------|-------------------|
| Rubric scoring / coaching | 40 coach examples (weak + strong pairs) |
| Question generation | 20 question-writer examples (all station types) |
| Model answers | 20 DPO preferred-answer examples |
| Step coaching | Signpost framework + archetype knowledge |
| Follow-ups, mutations, extraction | Archetype + framework knowledge |
    """)

    st.markdown("---")
    st.markdown("### Training Data Files")
    files_info = {
        "mmi_sft_coach.jsonl": "40 coach/rubric examples (injected into rubric scoring)",
        "mmi_sft_questionwriter.jsonl": "20 question-writer examples (injected into question gen)",
        "mmi_dpo_answers.jsonl": "20 preferred answers (injected into model answer gen)",
    }
    for fname, desc in files_info.items():
        root_fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", fname)
        exists = os.path.exists(root_fpath)
        if exists:
            with open(root_fpath, "r", encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
            st.success(f"**{fname}** — {line_count} examples — *{desc}*")
        else:
            st.error(f"**{fname}** — NOT FOUND — *{desc}*")

# ─── Data Management ─────────────────────────────────────────────
with tab_data:
    st.subheader("💾 Data Management")

    # ── Seed / Export ──
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("### Seed Data")
        st.markdown(f"Current question count: **{count_questions()}**")
        if st.button("🔄 Reload Seed + Training Questions"):
            n = load_seed_questions(force=True)
            st.success(f"Reloaded {n} questions (seed + training data).")
            st.rerun()

    with col_d2:
        st.markdown("### Export")
        all_q = get_all_questions()
        if all_q:
            export_data = json.dumps(all_q, indent=2, default=str)
            st.download_button(
                "📥 Export Questions (JSON)",
                data=export_data,
                file_name="mmi_questions.json",
                mime="application/json",
            )

    st.markdown("---")

    # ── Question Statistics ──
    all_q = get_all_questions()
    if all_q:
        st.markdown("### Question Statistics")
        source_counts: dict[str, int] = {}
        arch_counts: dict[str, int] = {}
        for q in all_q:
            source_counts[q["source_pack"]] = source_counts.get(q["source_pack"], 0) + 1
            arch_counts[q["archetype"]] = arch_counts.get(q["archetype"], 0) + 1

        ca, cb = st.columns(2)
        with ca:
            st.markdown("**By Source:**")
            for src, cnt in sorted(source_counts.items()):
                st.markdown(f"- {src}: **{cnt}**")
        with cb:
            st.markdown("**By Archetype:**")
            for arch, cnt in sorted(arch_counts.items()):
                st.markdown(f"- {arch.replace('_', ' ').title()}: **{cnt}**")

    st.markdown("---")

    # ── User Profiles ──
    st.markdown("### 👥 User Profiles")
    users = get_all_users()
    if users:
        for u in users:
            uc1, uc2, uc3 = st.columns([1, 3, 1])
            with uc1:
                st.markdown(f"### {u['avatar']}")
            with uc2:
                att_count = len(get_user_attempts(u["id"], limit=10000))
                st.markdown(f"**{u['display_name']}**")
                st.caption(f"{att_count} attempts · Created {u['created_at'][:10]}")
            with uc3:
                if u["id"] != user_id:  # Can't delete yourself
                    if st.button("🗑️", key=f"delusr_{u['id']}"):
                        delete_user(u["id"])
                        st.success(f"Deleted profile '{u['display_name']}'.")
                        st.rerun()
                else:
                    st.caption("(you)")
    else:
        st.info("No user profiles yet.")

    st.markdown("---")

    # ── Danger Zone ──
    st.markdown("### ⚠️ Danger Zone")
    if st.button("🗑️ Clear All Data", type="secondary"):
        st.session_state["confirm_clear"] = True

    if st.session_state.get("confirm_clear"):
        st.warning("This will delete **all** attempts, SRS data, skills, and questions.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("⚠️ Yes, delete everything", type="primary"):
                conn = get_conn()
                conn.executescript("""
                    DELETE FROM attempts;
                    DELETE FROM srs;
                    DELETE FROM user_skill;
                    DELETE FROM questions;
                """)
                conn.commit()
                conn.close()
                st.session_state["confirm_clear"] = False
                st.success("All data cleared.")
                st.rerun()
        with cc2:
            if st.button("Cancel"):
                st.session_state["confirm_clear"] = False
                st.rerun()

st.markdown("---")
st.caption("MMI Prep · Admin Panel")
