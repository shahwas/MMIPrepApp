"""
Pydantic models and JSON schemas for structured LLM outputs.
Enhanced with signpost framework, micro-upgrades, and richer coaching
derived from MMI training data (DPO + SFT).
"""

from pydantic import BaseModel, Field
from typing import Optional

# ─── The 7-Step Signpost Framework (from training data) ──────────
SIGNPOST_FRAMEWORK = [
    "One-sentence recap + clarify missing facts",
    "Stakeholders + competing values",
    "Emotions (yours + others) and how you would regulate them",
    "Principles (safety, autonomy, beneficence, fairness, confidentiality where relevant)",
    "Options (at least 2) with pros/cons and tradeoffs",
    "Recommendation + immediate next steps",
    "Reflection: what you'd do differently next time / what you'd learn",
]


# ─── StepCoach (nano model) ──────────────────────────────────────

class StepCoach(BaseModel):
    step_complete: bool
    missing_points: list[str]
    one_best_nudge: str
    human_marker_suggestion: str
    next_step_id: str
    signpost_step_hint: str  # Which signpost framework step applies here


STEP_COACH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "step_complete": {"type": "boolean"},
        "missing_points": {"type": "array", "items": {"type": "string"}},
        "one_best_nudge": {"type": "string"},
        "human_marker_suggestion": {"type": "string"},
        "next_step_id": {"type": "string"},
        "signpost_step_hint": {"type": "string"},
    },
    "required": ["step_complete", "missing_points", "one_best_nudge", "human_marker_suggestion", "next_step_id", "signpost_step_hint"],
}


# ─── FinalRubric (mini model) — Enhanced from training data ──────

class DetailedScores(BaseModel):
    """0-2 each (granular) matching training data rubric."""
    structure: int = Field(ge=0, le=2)
    empathy: int = Field(ge=0, le=2)
    information_gathering: int = Field(ge=0, le=2)
    reasoning: int = Field(ge=0, le=2)
    professionalism: int = Field(ge=0, le=2)


class ExpandedScores(BaseModel):
    """0-5 each (6 dimensions) for detailed skill tracking."""
    structure: int = Field(ge=0, le=5)
    empathy: int = Field(ge=0, le=5)
    perspective: int = Field(ge=0, le=5)
    reasoning: int = Field(ge=0, le=5)
    actionability: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)


class FinalRubric(BaseModel):
    overall_score_0_to_10: float
    rubric_0_to_2_each: DetailedScores
    scores: ExpandedScores
    what_worked: list[str]
    what_to_improve: list[str]
    top_3_improvements: list[str]
    best_line_you_said: str
    rewrite_30s: str
    rewrite_90s: str
    recommended_signpost_framework: list[str]
    micro_upgrade: str
    interviewer_followups: list[str]


FINAL_RUBRIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overall_score_0_to_10": {"type": "number"},
        "rubric_0_to_2_each": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "structure": {"type": "integer"},
                "empathy": {"type": "integer"},
                "information_gathering": {"type": "integer"},
                "reasoning": {"type": "integer"},
                "professionalism": {"type": "integer"},
            },
            "required": ["structure", "empathy", "information_gathering", "reasoning", "professionalism"],
        },
        "scores": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "structure": {"type": "integer"},
                "empathy": {"type": "integer"},
                "perspective": {"type": "integer"},
                "reasoning": {"type": "integer"},
                "actionability": {"type": "integer"},
                "clarity": {"type": "integer"},
            },
            "required": ["structure", "empathy", "perspective", "reasoning", "actionability", "clarity"],
        },
        "what_worked": {"type": "array", "items": {"type": "string"}},
        "what_to_improve": {"type": "array", "items": {"type": "string"}},
        "top_3_improvements": {"type": "array", "items": {"type": "string"}},
        "best_line_you_said": {"type": "string"},
        "rewrite_30s": {"type": "string"},
        "rewrite_90s": {"type": "string"},
        "recommended_signpost_framework": {"type": "array", "items": {"type": "string"}},
        "micro_upgrade": {"type": "string"},
        "interviewer_followups": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "overall_score_0_to_10", "rubric_0_to_2_each", "scores",
        "what_worked", "what_to_improve", "top_3_improvements",
        "best_line_you_said", "rewrite_30s", "rewrite_90s",
        "recommended_signpost_framework", "micro_upgrade", "interviewer_followups"
    ],
}


# ─── QuestionExtractor (for PDF ingestion) ──────────────────────

class QuestionExtractor(BaseModel):
    is_question: bool
    archetype_guess: str
    clean_prompt_text: str
    tags: list[str]


QUESTION_EXTRACTOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_question": {"type": "boolean"},
        "archetype_guess": {"type": "string"},
        "clean_prompt_text": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_question", "archetype_guess", "clean_prompt_text", "tags"],
}


# ─── DifficultyMutator ──────────────────────────────────────────

class MutatedPrompt(BaseModel):
    mutated_prompt: str
    mutation_notes: str


MUTATED_PROMPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "mutated_prompt": {"type": "string"},
        "mutation_notes": {"type": "string"},
    },
    "required": ["mutated_prompt", "mutation_notes"],
}
