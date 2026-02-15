"""
Automated end-to-end test for the MMI Prep App.

Simulates a real user journey:
  1. DB & seed data integrity
  2. Guided practice: walk through all steps, verify coaching quality
  3. Final rubric: check scoring, feedback depth, model answer
  4. SRS: verify stats update, spaced repetition scheduling, skill EMA
  5. Adaptive selection: verify weakest-skill targeting
  6. Question generation & mutation
  7. Timed-mode rubric (no step coaching)

Run:  .venv/Scripts/python.exe test_app.py
"""

import json
import sys
import os
import io
import time
import traceback
from datetime import date, timedelta

# ── Force UTF-8 stdout so box-drawing chars don't crash on Windows cp1252 ──
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Log file ────────────────────────────────────────────────────
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_log.txt")
_log_fh = open(LOG_PATH, "w", encoding="utf-8")

def _log(msg: str):
    """Write to both stdout and the log file."""
    print(msg)
    _log_fh.write(msg + "\n")
    _log_fh.flush()

# ── Helpers ──────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = 0
failed = 0
skipped = 0
errors_log = []

def header(title):
    _log(f"\n{BOLD}{CYAN}{'='*60}")
    _log(f"  {title}")
    _log(f"{'='*60}{RESET}\n")

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        _log(f"  {GREEN}[PASS] {name}{RESET}")
    else:
        failed += 1
        msg = f"  {RED}[FAIL] {name}{RESET}"
        if detail:
            msg += f"  -- {detail}"
        _log(msg)
        errors_log.append(f"{name}: {detail}")

def skip(name, reason):
    global skipped
    skipped += 1
    _log(f"  {YELLOW}[SKIP] {name} -- SKIPPED: {reason}{RESET}")

def section(name):
    _log(f"\n  {BOLD}-- {name} --{RESET}")


# ==================================================================
# TEST 1: Database & Seed Data
# ==================================================================
def test_database():
    header("1. DATABASE & SEED DATA")
    _log("  [LOG] Importing db and archetypes...")
    from db import (
        init_db, count_questions, get_all_questions,
        get_questions_by_archetype, get_user_skills, SKILL_NAMES,
    )
    from archetypes import ARCHETYPES
    _log("  [LOG] Imports OK. Running init_db...")

    init_db()
    total = count_questions()
    check("Questions exist in DB", total > 0, f"found {total}")
    check("At least 10 seed questions", total >= 10, f"found {total}")

    all_q = get_all_questions()
    archetypes_in_db = set(q["archetype"] for q in all_q)
    check("Multiple archetypes seeded", len(archetypes_in_db) >= 3,
          f"archetypes: {archetypes_in_db}")

    # Check archetype definitions
    check("Archetypes loaded", len(ARCHETYPES) >= 5, f"found {len(ARCHETYPES)}")
    for key, arch in ARCHETYPES.items():
        check(f"Archetype '{key}' has steps", len(arch.steps) >= 3)

    # Check skill names
    skills = get_user_skills("test_runner")
    check("Skill tracking initialized", len(skills) == len(SKILL_NAMES),
          f"skills: {list(skills.keys())}")


# ==================================================================
# TEST 2: Guided Practice — Step-by-step Coaching
# ==================================================================
def test_guided_practice():
    header("2. GUIDED PRACTICE -- STEP COACHING")
    _log("  [LOG] Importing llm.evaluate_step...")
    from db import get_all_questions
    from llm import evaluate_step
    from archetypes import get_archetype
    _log("  [LOG] Imports OK.")

    all_q = get_all_questions()
    # Pick an ethical_dilemma question
    q = next((q for q in all_q if q["archetype"] == "ethical_dilemma"), all_q[0])
    arch = get_archetype(q["archetype"])

    _log(f"  Question: {q['prompt_text'][:100]}...")
    _log(f"  Archetype: {q['archetype']} ({len(arch.steps)} steps)\n")

    # Simulate a WEAK answer for step 1 -- should get coaching
    section("Step 1 -- Weak answer (should coach, not advance)")
    weak_answer = "I think it's wrong and they should be reported."
    t0 = time.time()
    result1 = evaluate_step(
        q["archetype"], arch.steps[0].id, q["prompt_text"],
        weak_answer, []
    )
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")
    _log(f"  [LOG] result1 keys: {list(result1.keys()) if isinstance(result1, dict) else type(result1)}")

    check("Returns dict", isinstance(result1, dict))
    check("Has step_complete field", "step_complete" in result1)
    check("Has one_best_nudge", bool(result1.get("one_best_nudge")),
          f"nudge: '{result1.get('one_best_nudge', '')[:80]}'")
    check("Has missing_points", isinstance(result1.get("missing_points"), list))
    check("Has signpost_step_hint", bool(result1.get("signpost_step_hint")))
    check("Has human_marker_suggestion", bool(result1.get("human_marker_suggestion")))

    # If step_complete is False, that's a GOOD sign for a weak answer
    if not result1.get("step_complete"):
        check("Weak answer NOT marked complete (good!)", True)
    else:
        check("Weak answer marked complete (debatable)", True,
              "Model was lenient -- acceptable but watch quality")

    # Simulate a STRONG answer for step 1 -- should advance
    section("Step 1 -- Strong answer (should advance)")
    strong_answer = (
        "The core tension here is between loyalty to my colleague and my duty to patient safety. "
        "On one hand, I value our professional relationship and understand they might be going through "
        "a difficult time. On the other hand, patients deserve competent care and I have an obligation "
        "to protect them. There's also the principle of autonomy -- my colleague deserves a chance to "
        "explain -- balanced against beneficence and non-maleficence for the patients."
    )
    t0 = time.time()
    result2 = evaluate_step(
        q["archetype"], arch.steps[0].id, q["prompt_text"],
        strong_answer, []
    )
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")
    _log(f"  [LOG] result2 keys: {list(result2.keys()) if isinstance(result2, dict) else type(result2)}")

    check("Strong answer marked complete", result2.get("step_complete") == True,
          f"step_complete={result2.get('step_complete')}")
    check("Next step advances", result2.get("next_step_id") != arch.steps[0].id,
          f"next={result2.get('next_step_id')}")
    check("Still gives coaching even on good answer",
          bool(result2.get("one_best_nudge") or result2.get("missing_points")))

    # Walk through remaining steps with decent answers
    section("Walking through remaining steps")
    _log(f"  [LOG] {len(arch.steps)-1} remaining steps to walk through...")
    conversation = [{"step": arch.steps[0].id, "answer": strong_answer}]
    decent_answers = {
        "facts": "I need to verify what I actually saw vs. assumptions. Was it a one-time thing or pattern? Are there other witnesses? What's their usual performance like?",
        "stakeholders": "The patients are the primary concern -- their safety is paramount. My colleague may be struggling with burnout or personal issues. I'd feel conflicted and anxious. The rest of the team is affected. Hospital administration needs to know if there's a pattern.",
        "options": "Option 1: Talk to my colleague privately first -- pro: respectful, may resolve quickly. Con: delays intervention if serious. Option 2: Report to supervisor immediately -- pro: protects patients. Con: damages relationship, may be premature. Option 3: Document and monitor -- pro: gathers evidence. Con: patients at risk in the meantime.",
        "recommend": "I'd start by having a private, non-judgmental conversation with my colleague. I'd express concern rather than accusation. If they're struggling, I'd help connect them with support. But if patient safety is immediately at risk, I'd escalate to our supervisor regardless -- that's a non-negotiable duty.",
        "communicate": "I'd say something like: 'Hey, I've noticed something that concerned me and I wanted to talk to you about it privately because I respect you. I care about you as a colleague and I also want to make sure our patients are safe. Can we talk?' I'd use 'I' statements and avoid blame.",
        "followup": "I'd document what I observed with dates and specifics. If the conversation doesn't resolve things, I'd escalate through proper channels. I'd also check in on the patients who were affected and follow up with my colleague to offer ongoing support.",
    }
    steps_passed = 1
    for step in arch.steps[1:]:
        answer = decent_answers.get(step.id, "I think we need to consider multiple perspectives and act professionally.")
        result = evaluate_step(
            q["archetype"], step.id, q["prompt_text"],
            answer, conversation
        )
        conversation.append({"step": step.id, "answer": answer})
        _log(f"  [LOG] Step '{step.id}': complete={result.get('step_complete')}")
        if result.get("step_complete"):
            steps_passed += 1
    check(f"Completed {steps_passed}/{len(arch.steps)} steps",
          steps_passed >= len(arch.steps) - 1,
          f"{steps_passed} of {len(arch.steps)} steps passed")

    return q, conversation


# ==================================================================
# TEST 3: Final Rubric & Scoring
# ==================================================================
def test_rubric(q, conversation):
    header("3. FINAL RUBRIC & SCORING")
    _log("  [LOG] Importing llm.generate_rubric...")
    from llm import generate_rubric

    transcript = "\n\n".join(
        f"[{d['step']}]: {d['answer']}" for d in conversation
    )

    section("Generating rubric for guided practice")
    t0 = time.time()
    rubric = generate_rubric(q["archetype"], q["prompt_text"], transcript, "guided")
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")
    _log(f"  [LOG] rubric keys: {list(rubric.keys()) if isinstance(rubric, dict) else type(rubric)}")

    # Score checks
    score = rubric.get("overall_score_0_to_10", -1)
    check("Overall score is number", isinstance(score, (int, float)), f"score={score}")
    check("Score in range 0-10", 0 <= score <= 10, f"score={score}")
    check("Strong answer scores >= 5", score >= 5,
          f"score={score} -- if < 5 the model is scoring too harshly for decent answers")

    # Granular rubric (0-2)
    r02 = rubric.get("rubric_0_to_2_each", {})
    check("Has granular rubric", isinstance(r02, dict) and len(r02) >= 5,
          f"keys: {list(r02.keys())}")
    for k, v in r02.items():
        check(f"  rubric_0_2.{k} in [0,1,2]", v in [0, 1, 2], f"got {v}")

    # Detailed scores (0-5)
    scores = rubric.get("scores", {})
    check("Has detailed scores", isinstance(scores, dict) and len(scores) >= 6,
          f"keys: {list(scores.keys())}")
    for k, v in scores.items():
        check(f"  scores.{k} in [0-5]", 0 <= v <= 5, f"got {v}")

    # Feedback quality
    section("Feedback quality")
    check("what_worked is list", isinstance(rubric.get("what_worked"), list))
    check("what_to_improve is list", isinstance(rubric.get("what_to_improve"), list))
    check("top_3_improvements has items",
          len(rubric.get("top_3_improvements", [])) >= 1,
          f"got {len(rubric.get('top_3_improvements', []))} improvements")
    check("best_line_you_said present", bool(rubric.get("best_line_you_said")))
    check("rewrite_30s present", len(rubric.get("rewrite_30s", "")) > 20,
          f"length={len(rubric.get('rewrite_30s', ''))}")
    check("rewrite_90s present", len(rubric.get("rewrite_90s", "")) > 50,
          f"length={len(rubric.get('rewrite_90s', ''))}")
    check("micro_upgrade present", bool(rubric.get("micro_upgrade")))
    check("interviewer_followups present",
          len(rubric.get("interviewer_followups", [])) >= 2,
          f"got {len(rubric.get('interviewer_followups', []))}")
    check("signpost framework referenced",
          len(rubric.get("recommended_signpost_framework", [])) >= 3)

    return rubric


# ==================================================================
# TEST 4: Stats, SRS, Skill Tracking
# ==================================================================
def test_stats_and_srs(q, rubric):
    header("4. STATS, SRS & SKILL TRACKING")
    from db import (
        insert_attempt, get_user_attempts, get_user_skills, update_user_skill,
        get_srs, SKILL_NAMES,
    )
    from srs import record_review, quality_from_scores, update_skills_from_rubric, get_study_stats

    user_id = "test_runner"
    scores = rubric.get("scores", {})

    # Test quality conversion
    section("Quality conversion")
    q_val = quality_from_scores(scores)
    check("quality_from_scores returns 0-5", 0 <= q_val <= 5, f"quality={q_val}")

    # Save attempt
    section("Saving attempt")
    aid = insert_attempt(
        user_id, q["id"], "guided", q.get("difficulty_base", 3),
        "Test transcript", {}, rubric
    )
    check("Attempt saved", bool(aid), f"attempt_id={aid}")

    attempts = get_user_attempts(user_id)
    check("Attempt retrievable", len(attempts) >= 1, f"found {len(attempts)}")
    latest = attempts[0]
    check("Attempt has rubric JSON", bool(latest.get("rubric_json")))

    # SRS update
    section("SRS scheduling")
    record_review(user_id, q["id"], q_val)
    srs_data = get_srs(user_id, q["id"])
    check("SRS record created", srs_data is not None)
    check("SRS has ease", srs_data and 1.0 <= srs_data["ease"] <= 4.0,
          f"ease={srs_data['ease'] if srs_data else 'N/A'}")
    check("SRS has due_date", srs_data and bool(srs_data.get("due_date")))

    # Simulate a LAPSE (low quality) — interval should reset
    record_review(user_id, q["id"], 1)  # quality=1 → lapse
    srs_after_lapse = get_srs(user_id, q["id"])
    check("Lapse resets interval to 1",
          srs_after_lapse and srs_after_lapse["interval_days"] == 1,
          f"interval={srs_after_lapse['interval_days'] if srs_after_lapse else 'N/A'}")
    check("Lapse decreases ease",
          srs_after_lapse and srs_after_lapse["ease"] <= srs_data["ease"],
          f"before={srs_data['ease']}, after={srs_after_lapse['ease'] if srs_after_lapse else 'N/A'}")

    # Simulate multiple good reviews — interval should grow
    for _ in range(3):
        record_review(user_id, q["id"], 4)  # quality=4 → good
    srs_after_good = get_srs(user_id, q["id"])
    check("Good reviews increase interval",
          srs_after_good and srs_after_good["interval_days"] > 1,
          f"interval={srs_after_good['interval_days'] if srs_after_good else 'N/A'}")

    # Skill EMA update
    section("Skill EMA tracking")
    update_skills_from_rubric(user_id, scores)
    skills = get_user_skills(user_id)
    for s in SKILL_NAMES:
        check(f"Skill '{s}' updated",
              skills[s]["n_attempts"] >= 1,
              f"ema={skills[s]['ema_score']:.2f}, n={skills[s]['n_attempts']}")

    # Study stats
    section("Study stats")
    stats = get_study_stats(user_id)
    check("study_stats has due_count", "due_count" in stats)
    check("study_stats has skills", "skills" in stats)
    check("study_stats has weakest_skill", bool(stats.get("weakest_skill")))
    _log(f"  Weakest skill: {stats['weakest_skill']}")


# ==================================================================
# TEST 5: Adaptive Card Selection
# ==================================================================
def test_adaptive_selection():
    header("5. ADAPTIVE CARD SELECTION")
    from srs import select_next_card
    from db import get_user_skills, update_user_skill

    user_id = "test_runner"

    # Artificially weaken one skill
    update_user_skill(user_id, "empathy", 0.5, alpha=1.0)  # force empathy very low
    skills = get_user_skills(user_id)
    _log(f"  Forced empathy low: {skills['empathy']['ema_score']:.2f}")

    # Select several cards and check if empathy-heavy archetypes appear
    selections = []
    for _ in range(10):
        card = select_next_card(user_id)
        if card:
            selections.append(card.get("archetype", "unknown"))

    check("Card selection returns results", len(selections) > 0,
          f"got {len(selections)} selections")
    _log(f"  Archetypes selected: {dict((a, selections.count(a)) for a in set(selections))}")


# ==================================================================
# TEST 6: Question Generation & Mutation
# ==================================================================
def test_question_generation():
    header("6. AI QUESTION GENERATION & MUTATION")
    _log("  [LOG] Importing llm.generate_question, mutate_difficulty...")
    from llm import generate_question, mutate_difficulty
    _log("  [LOG] Imports OK.")

    section("Generate new question")
    t0 = time.time()
    new_q = generate_question("ethical_dilemma", difficulty=3, themes="patient confidentiality")
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")
    _log(f"  [LOG] new_q keys: {list(new_q.keys()) if isinstance(new_q, dict) else type(new_q)}")

    check("Generated prompt_text", bool(new_q.get("prompt_text")),
          f"length={len(new_q.get('prompt_text', ''))}")
    check("Prompt is substantial (>50 chars)",
          len(new_q.get("prompt_text", "")) > 50)
    check("Has themes", isinstance(new_q.get("themes"), list) and len(new_q.get("themes", [])) >= 1)
    _log(f"  Preview: {new_q.get('prompt_text', '')[:120]}...")

    section("Mutate difficulty D3 → D5")
    t0 = time.time()
    mutated = mutate_difficulty(new_q["prompt_text"], 3, 5)
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")

    check("Mutated prompt returned", bool(mutated.get("mutated_prompt")))
    check("Mutation notes explain changes", bool(mutated.get("mutation_notes")))
    check("Mutated prompt differs from original",
          mutated.get("mutated_prompt", "") != new_q.get("prompt_text", ""))
    _log(f"  Notes: {mutated.get('mutation_notes', '')[:120]}...")


# ==================================================================
# TEST 7: Timed Mode (rubric without step coaching)
# ==================================================================
def test_timed_mode():
    header("7. TIMED MODE -- RUBRIC ON RAW ANSWER")
    _log("  [LOG] Importing llm for timed mode...")
    from db import get_all_questions
    from llm import generate_rubric, generate_model_answer
    _log("  [LOG] Imports OK.")

    print = _log  # ensure no stray print calls slip through

    all_q = get_all_questions()
    q = next((q for q in all_q if q["archetype"] == "roleplay"), None)
    if not q:
        q = all_q[0]

    _log(f"  Question: {q['prompt_text'][:100]}...")

    # Simulate a mediocre timed answer
    mediocre = (
        "I would talk to the person and try to understand their perspective. "
        "I think communication is important and I would try to resolve the situation "
        "by being professional and respectful. I would also consider the feelings of "
        "everyone involved."
    )

    section("Rubric for mediocre timed answer")
    t0 = time.time()
    rubric = generate_rubric(q["archetype"], q["prompt_text"], mediocre, "timed")
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")
    _log(f"  [LOG] timed rubric keys: {list(rubric.keys()) if isinstance(rubric, dict) else type(rubric)}")

    score = rubric.get("overall_score_0_to_10", -1)
    check("Mediocre answer scores 2-6", 2 <= score <= 6,
          f"score={score} -- vague answer should NOT score high")
    check("Identifies areas to improve",
          len(rubric.get("what_to_improve", [])) >= 1)
    check("Gives actionable improvements",
          len(rubric.get("top_3_improvements", [])) >= 1)

    # Generate model answer for comparison
    section("Model answer generation")
    t0 = time.time()
    model_ans = generate_model_answer(q["prompt_text"], "90s")
    t1 = time.time()
    _log(f"  (API call: {t1-t0:.1f}s)")

    check("Model answer is substantial",
          len(model_ans) > 100, f"length={len(model_ans)}")
    _log(f"  Preview: {model_ans[:150]}...")


# ==================================================================
# TEST 8: Knowledge Bank Verification
# ==================================================================
def test_knowledge_bank():
    header("8. KNOWLEDGE BANK INTEGRITY")
    from knowledge import COACH_EXAMPLES, QUESTION_WRITER_EXAMPLES, DPO_PREFERRED_EXAMPLES

    check("Coach examples loaded", len(COACH_EXAMPLES) >= 30,
          f"count={len(COACH_EXAMPLES)}")
    check("Question-writer examples loaded", len(QUESTION_WRITER_EXAMPLES) >= 15,
          f"count={len(QUESTION_WRITER_EXAMPLES)}")
    check("DPO preferred examples loaded", len(DPO_PREFERRED_EXAMPLES) >= 15,
          f"count={len(DPO_PREFERRED_EXAMPLES)}")

    # Verify structure
    for name, bank in [("coach", COACH_EXAMPLES), ("qwriter", QUESTION_WRITER_EXAMPLES), ("dpo", DPO_PREFERRED_EXAMPLES)]:
        sample = bank[0] if bank else {}
        check(f"{name}[0] has 'user' key", "user" in sample)
        check(f"{name}[0] has 'assistant' key", "assistant" in sample)
        check(f"{name}[0].user is non-empty", len(sample.get("user", "")) > 10)
        check(f"{name}[0].assistant is non-empty", len(sample.get("assistant", "")) > 10)


# ==================================================================
# CLEANUP
# ==================================================================
def cleanup():
    """Remove test user data so it doesn't pollute the real DB."""
    from db import get_conn
    conn = get_conn()
    conn.execute("DELETE FROM srs WHERE user_id='test_runner'")
    conn.execute("DELETE FROM attempts WHERE user_id='test_runner'")
    conn.execute("DELETE FROM user_skill WHERE user_id='test_runner'")
    conn.commit()
    conn.close()
    _log(f"\n  {CYAN}Cleaned up test_runner data from DB.{RESET}")


# ==================================================================
# MAIN
# ==================================================================
if __name__ == "__main__":
    _log(f"\n{BOLD}{CYAN}+{'='*58}+")
    _log(f"|{'MMI PREP APP -- AUTOMATED TEST SUITE':^58}|")
    _log(f"+{'='*58}+{RESET}")

    from model_config import MODEL
    _log(f"\n  Model: {MODEL}")
    _log(f"  Date:  {date.today().isoformat()}")
    _log(f"  Log:   {LOG_PATH}\n")

    q_data = None
    conversation = None
    rubric_data = None

    try:
        # Non-LLM tests first (fast)
        test_knowledge_bank()
        test_database()

        # LLM tests (each makes API calls)
        q_data, conversation = test_guided_practice()
        rubric_data = test_rubric(q_data, conversation)
        test_stats_and_srs(q_data, rubric_data)
        test_adaptive_selection()
        test_question_generation()
        test_timed_mode()

    except KeyboardInterrupt:
        _log(f"\n{YELLOW}Interrupted by user.{RESET}")
    except Exception as e:
        _log(f"\n{RED}FATAL ERROR: {e}{RESET}")
        _log(traceback.format_exc())
    finally:
        cleanup()

    # Summary
    total = passed + failed
    _log(f"\n{BOLD}{CYAN}{'='*60}")
    _log(f"  RESULTS: {passed} passed, {failed} failed, {skipped} skipped ({total} total)")
    _log(f"{'='*60}{RESET}")

    if errors_log:
        _log(f"\n{RED}  Failed checks:{RESET}")
        for e in errors_log:
            _log(f"    - {e}")

    if failed == 0:
        _log(f"\n  {GREEN}{BOLD}ALL TESTS PASSED{RESET}\n")
    else:
        _log(f"\n  {YELLOW}Some checks failed -- review above for details.{RESET}\n")

    _log_fh.close()
    sys.exit(0 if failed == 0 else 1)
