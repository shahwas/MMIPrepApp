"""
Load seed questions from YAML and JSONL training data into the database.
"""

import json
import os
import yaml
from db import insert_question, count_questions, get_conn

SEED_FILE = os.path.join(os.path.dirname(__file__), "seed_questions.yaml")
JSONL_QUESTION_FILE = os.path.join(os.path.dirname(__file__), "mmi_sft_questionwriter.jsonl")
JSONL_DPO_FILE = os.path.join(os.path.dirname(__file__), "mmi_dpo_answers.jsonl")


def _extract_questions_from_jsonl() -> list[dict]:
    """Extract unique questions from the SFT question-writer and DPO training files."""
    questions = []
    seen_prompts = set()

    # Extract from question writer JSONL
    if os.path.exists(JSONL_QUESTION_FILE):
        with open(JSONL_QUESTION_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    messages = data.get("messages", [])
                    # The assistant message contains the generated question
                    assistant_msg = next((m["content"] for m in messages if m["role"] == "assistant"), "")
                    user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")

                    if not assistant_msg:
                        continue

                    # Clean up: remove trailing theme lines
                    prompt = assistant_msg.strip()
                    # Remove "Theme(s):" suffix lines
                    lines = prompt.split("\n")
                    clean_lines = []
                    for ln in lines:
                        if ln.strip().startswith("Theme(s):"):
                            break
                        clean_lines.append(ln)
                    prompt = "\n".join(clean_lines).strip()

                    # Remove page numbers (standalone numbers on a line)
                    import re
                    prompt = re.sub(r'\n\s*\d{2,3}\s*\n', '\n', prompt)
                    prompt = prompt.strip()

                    if len(prompt) < 20 or prompt in seen_prompts:
                        continue
                    seen_prompts.add(prompt)

                    # Determine archetype from user message
                    archetype = "ethical_dilemma"  # default
                    user_lower = user_msg.lower()
                    if "acting" in user_lower:
                        archetype = "roleplay"
                    elif "personal" in user_lower:
                        archetype = "personal"
                    elif "quirky" in user_lower:
                        archetype = "personal"
                    elif "written" in user_lower:
                        archetype = "reflection"
                    elif "quote" in user_lower:
                        archetype = "reflection"
                    elif "picture" in user_lower:
                        archetype = "reflection"
                    elif "policy" in user_lower:
                        archetype = "policy"
                    elif "patient autonomy" in user_lower:
                        archetype = "consent_capacity"
                    elif "conflict resolution" in user_lower:
                        archetype = "roleplay"

                    # Extract themes
                    themes = []
                    for kw in ["ethical dilemma", "conflict resolution", "patient autonomy",
                               "informed consent", "professionalism", "non-judgmental",
                               "patient confidentiality", "legal awareness", "problem-solving"]:
                        if kw in user_lower:
                            themes.append(kw)

                    questions.append({
                        "archetype": archetype,
                        "difficulty": 3,
                        "prompt": prompt,
                        "tags": themes if themes else ["training-data"],
                    })
                except (json.JSONDecodeError, StopIteration):
                    continue

    # Extract from DPO answers JSONL (questions from the user messages)
    if os.path.exists(JSONL_DPO_FILE):
        with open(JSONL_DPO_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    messages = data.get("input", {}).get("messages", [])
                    user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")

                    if not user_msg:
                        continue

                    prompt = user_msg.strip()
                    # Remove page numbers
                    import re
                    prompt = re.sub(r'\n\s*\d{2,3}\s*\n', '\n', prompt)
                    prompt = re.sub(r'\n\d{2,3}$', '', prompt)
                    prompt = prompt.strip()

                    if len(prompt) < 20 or prompt in seen_prompts:
                        continue
                    seen_prompts.add(prompt)

                    questions.append({
                        "archetype": "ethical_dilemma",
                        "difficulty": 3,
                        "prompt": prompt,
                        "tags": ["training-data", "dpo"],
                    })
                except (json.JSONDecodeError, StopIteration):
                    continue

    return questions


def load_seed_questions(force: bool = False):
    """Load seed questions from YAML and JSONL training data. Skips if already loaded unless force=True."""
    if not force and count_questions() > 0:
        return count_questions()

    if force:
        conn = get_conn()
        conn.execute("DELETE FROM questions WHERE source_pack IN ('seed', 'training-data')")
        conn.commit()
        conn.close()

    count = 0

    # Load YAML seeds
    if os.path.exists(SEED_FILE):
        with open(SEED_FILE, "r", encoding="utf-8") as f:
            questions = yaml.safe_load(f)

        if questions:
            for q in questions:
                insert_question(
                    archetype=q["archetype"],
                    difficulty_base=q["difficulty"],
                    prompt_text=q["prompt"],
                    tags=q.get("tags", []),
                    source_pack="seed",
                )
                count += 1

    # Load JSONL training data questions
    jsonl_questions = _extract_questions_from_jsonl()
    for q in jsonl_questions:
        # Check for duplicates (rough match by first 80 chars)
        conn = get_conn()
        existing = conn.execute(
            "SELECT id FROM questions WHERE prompt_text LIKE ?",
            (q["prompt"][:80] + "%",)
        ).fetchone()
        conn.close()

        if not existing:
            insert_question(
                archetype=q["archetype"],
                difficulty_base=q["difficulty"],
                prompt_text=q["prompt"],
                tags=q.get("tags", []),
                source_pack="training-data",
            )
            count += 1

    return count


if __name__ == "__main__":
    n = load_seed_questions(force=True)
    print(f"Loaded {n} seed questions.")
