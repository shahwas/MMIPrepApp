"""
Model Configuration - Single model: gpt-5-mini.

All coaching, rubric scoring, question generation, mutations, and follow-ups
use gpt-5-mini with all training examples injected as in-context knowledge.
No fine-tuning needed.
"""

MODEL = "gpt-5-mini-2025-08-07"

# Kept for backward compat with Admin page
FINE_TUNED_KEYS = {}


def get_model(slot: str = "") -> str:
    return MODEL


def get_all_models() -> dict:
    return {"model": MODEL}


def set_fine_tuned_model(slot: str, model_id: str):
    pass  # no-op


def remove_fine_tuned_model(slot: str):
    pass  # no-op
