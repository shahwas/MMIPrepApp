"""
Knowledge Bank - Loads ALL training examples from JSONL files at import time.
These are injected as few-shot context into every LLM call so the model
behaves as if fine-tuned, without needing actual fine-tuning.

Files loaded:
  - mmi_sft_coach.jsonl      (40 coach/rubric examples)
  - mmi_sft_questionwriter.jsonl (20 question-generation examples)
  - mmi_dpo_answers.jsonl     (20 preferred-vs-rejected answer pairs)
"""

import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_jsonl(filename: str) -> list[dict]:
    path = os.path.join(_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Coach / Rubric examples ─────────────────────────────────────
# The JSONL has an 8-key JSON schema; llm.py's FINAL_RUBRIC_SCHEMA has 12 keys.
# We bridge the gap by expanding each JSONL example to match the full schema
# so few-shot format and tone reinforce each other instead of conflicting.
_raw_coach = _load_jsonl("mmi_sft_coach.jsonl")


def _expand_coach_example(raw_json_str: str) -> str:
    """Transform JSONL coach output to match FINAL_RUBRIC_SCHEMA exactly."""
    try:
        d = json.loads(raw_json_str)
    except json.JSONDecodeError:
        return raw_json_str

    # Map the 0-2 granular rubric to approximate 0-5 detailed scores
    r02 = d.get("rubric_0_to_2_each", {})
    scale = 2.5  # multiply 0-2 by 2.5 to get 0-5 range
    expanded_scores = {
        "structure": min(5, round(r02.get("structure", 1) * scale)),
        "empathy": min(5, round(r02.get("empathy", 1) * scale)),
        "perspective": min(5, round(r02.get("reasoning", 1) * scale)),  # reasoning ≈ perspective
        "reasoning": min(5, round(r02.get("reasoning", 1) * scale)),
        "actionability": min(5, round(r02.get("information_gathering", 1) * scale)),
        "clarity": min(5, round(r02.get("professionalism", 1) * scale)),
    }

    # Build the full schema with sensible defaults for missing fields
    overall = d.get("overall_score_0_to_10", 5.0)
    full = {
        "overall_score_0_to_10": overall,
        "rubric_0_to_2_each": r02,
        "scores": expanded_scores,
        "what_worked": d.get("what_worked", []),
        "what_to_improve": d.get("what_to_improve", []),
        "top_3_improvements": d.get("what_to_improve", [])[:3] or ["Be more specific"],
        "best_line_you_said": "N/A",
        "rewrite_30s": d.get("micro_upgrade", ""),
        "rewrite_90s": "",
        "recommended_signpost_framework": d.get("recommended_signpost_framework", []),
        "micro_upgrade": d.get("micro_upgrade", ""),
        "interviewer_followups": [],
    }
    return json.dumps(full)


COACH_EXAMPLES: list[dict] = []
for row in _raw_coach:
    msgs = row.get("messages", [])
    user_msg = next((m["content"] for m in msgs if m["role"] == "user"), None)
    asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), None)
    if user_msg and asst_msg:
        COACH_EXAMPLES.append({
            "user": user_msg,
            "assistant": _expand_coach_example(asst_msg),
        })


# ── Question-writer examples ────────────────────────────────────
# The JSONL assistant output is raw prompt text, but llm.py's QUESTION_GEN_SCHEMA
# expects {"prompt_text": str, "themes": [str]}.  We wrap accordingly.
_raw_qw = _load_jsonl("mmi_sft_questionwriter.jsonl")


def _wrap_qwriter_example(user_msg: str, raw_prompt: str) -> str:
    """Wrap raw prompt text into the JSON schema llm.py expects."""
    # Extract themes from the user message (e.g. "Theme(s): ethical dilemma, ...")
    themes = []
    for line in user_msg.split("\n"):
        if line.lower().startswith("theme"):
            _, _, val = line.partition(":")
            themes = [t.strip() for t in val.split(",") if t.strip()]
            break
    if not themes:
        themes = ["general"]
    return json.dumps({"prompt_text": raw_prompt.strip(), "themes": themes})


QUESTION_WRITER_EXAMPLES: list[dict] = []
for row in _raw_qw:
    msgs = row.get("messages", [])
    user_msg = next((m["content"] for m in msgs if m["role"] == "user"), None)
    asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), None)
    if user_msg and asst_msg:
        QUESTION_WRITER_EXAMPLES.append({
            "user": user_msg,
            "assistant": _wrap_qwriter_example(user_msg, asst_msg),
        })


# ── DPO preferred answers (use preferred output as the example) ──
_raw_dpo = _load_jsonl("mmi_dpo_answers.jsonl")

DPO_PREFERRED_EXAMPLES: list[dict] = []
for row in _raw_dpo:
    # DPO format: input={messages: [...]}, preferred_output=[...], non_preferred_output=[...]
    inp = row.get("input", {})
    msgs = inp.get("messages", []) if isinstance(inp, dict) else inp
    preferred = row.get("preferred_output", [])
    user_msg = next((m["content"] for m in msgs if m["role"] == "user"), None)
    asst_msg = next((m["content"] for m in preferred if m["role"] == "assistant"), None)
    if user_msg and asst_msg:
        DPO_PREFERRED_EXAMPLES.append({"user": user_msg, "assistant": asst_msg})


# ── Summary ─────────────────────────────────────────────────────
KNOWLEDGE_SUMMARY = (
    f"Loaded {len(COACH_EXAMPLES)} coach examples, "
    f"{len(QUESTION_WRITER_EXAMPLES)} question-writer examples, "
    f"{len(DPO_PREFERRED_EXAMPLES)} preferred-answer examples."
)
