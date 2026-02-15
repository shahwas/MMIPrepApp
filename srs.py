"""
SM-2 Spaced Repetition Scheduler + Adaptive Card Selection.

SM-2 algorithm:
- After each review, update ease factor, interval, and repetitions
- Quality 0-2: reset (lapse), quality 3-5: advance

Adaptive selection:
- 70% from due cards (spaced repetition)
- 30% from weakest-skill targeted practice
"""

import random
from datetime import date, timedelta
from db import (
    get_srs, upsert_srs, get_due_cards, get_new_cards,
    get_weakest_skill, get_user_skills, get_all_questions,
    SKILL_NAMES, update_user_skill,
)
from archetypes import ARCHETYPES


def sm2_update(quality: int, ease: float, interval: int, repetitions: int) -> tuple[float, int, int]:
    """
    SM-2 algorithm update.
    quality: 0-5 (0-2 = fail/lapse, 3-5 = pass)
    Returns: (new_ease, new_interval, new_repetitions)
    """
    quality = max(0, min(5, quality))

    if quality < 3:
        # Lapse: reset repetitions, short interval
        return max(1.3, ease - 0.2), 1, 0

    # Success: update ease factor
    new_ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease = max(1.3, new_ease)

    if repetitions == 0:
        new_interval = 1
    elif repetitions == 1:
        new_interval = 6
    else:
        new_interval = round(interval * new_ease)

    return new_ease, new_interval, repetitions + 1


def record_review(user_id: str, question_id: str, quality: int):
    """Record a review and update SRS scheduling."""
    current = get_srs(user_id, question_id)
    if current:
        ease = current["ease"]
        interval = current["interval_days"]
        reps = current["repetitions"]
    else:
        ease = 2.5
        interval = 1
        reps = 0

    new_ease, new_interval, new_reps = sm2_update(quality, ease, interval, reps)
    due = (date.today() + timedelta(days=new_interval)).isoformat()

    upsert_srs(user_id, question_id, new_ease, new_interval, new_reps, due)


def quality_from_scores(scores: dict) -> int:
    """Convert rubric scores (0-5 each) to SM-2 quality (0-5)."""
    if not scores:
        return 2
    avg = sum(scores.values()) / len(scores)
    # Map average 0-5 to quality 0-5
    if avg < 1.0:
        return 0
    elif avg < 2.0:
        return 1
    elif avg < 2.5:
        return 2
    elif avg < 3.0:
        return 3
    elif avg < 4.0:
        return 4
    else:
        return 5


def update_skills_from_rubric(user_id: str, scores: dict):
    """Update user skill EMA scores from a rubric result."""
    for skill_name in SKILL_NAMES:
        if skill_name in scores:
            update_user_skill(user_id, skill_name, float(scores[skill_name]))


def select_next_card(user_id: str = "default") -> dict | None:
    """
    Adaptive card selection:
    70% chance: pick from due cards (spaced repetition)
    30% chance: pick from weakest-skill targeted practice
    Falls back to new cards if nothing is due.
    """
    roll = random.random()

    if roll < 0.70:
        # Due cards first
        due = get_due_cards(user_id, limit=20)
        if due:
            return random.choice(due)

    # Weakest skill targeting
    weakest = get_weakest_skill(user_id)
    # Find archetypes that emphasize this skill
    target_archetypes = []
    for key, arch in ARCHETYPES.items():
        if arch.skill_weights.get(weakest, 0) >= 1.1:
            target_archetypes.append(key)

    if target_archetypes:
        all_q = get_all_questions()
        candidates = [q for q in all_q if q["archetype"] in target_archetypes]
        if candidates:
            return random.choice(candidates)

    # Fallback: due cards
    due = get_due_cards(user_id, limit=20)
    if due:
        return random.choice(due)

    # Fallback: new cards
    new = get_new_cards(user_id, limit=10)
    if new:
        return random.choice(new)

    # Absolute fallback: any question
    all_q = get_all_questions()
    return random.choice(all_q) if all_q else None


def get_study_stats(user_id: str = "default") -> dict:
    """Get study statistics for the user."""
    due = get_due_cards(user_id, limit=1000)
    new = get_new_cards(user_id, limit=1000)
    skills = get_user_skills(user_id)
    weakest = get_weakest_skill(user_id)
    # Check if any skill has been assessed
    has_data = any(s["n_attempts"] > 0 for s in skills.values())

    return {
        "due_count": len(due),
        "new_count": len(new),
        "skills": skills,
        "weakest_skill": weakest,
        "has_skill_data": has_data,
    }
