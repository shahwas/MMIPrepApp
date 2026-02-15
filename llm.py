"""
OpenAI LLM integration - Single model: gpt-5-mini for everything.

All training data (coach, question-writer, DPO-preferred answers) is loaded
from knowledge.py and injected as few-shot examples so the model behaves
as if fine-tuned without any actual fine-tuning.
"""

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

from models import (
    STEP_COACH_SCHEMA,
    FINAL_RUBRIC_SCHEMA,
    QUESTION_EXTRACTOR_SCHEMA,
    MUTATED_PROMPT_SCHEMA,
    SIGNPOST_FRAMEWORK,
)
from archetypes import get_archetype, Archetype, Step
from model_config import get_model
from knowledge import (
    COACH_EXAMPLES,
    QUESTION_WRITER_EXAMPLES,
    DPO_PREFERRED_EXAMPLES,
)

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = get_model()


# =====================================================================
# Core caller
# =====================================================================

def _call_structured(system: str, user: str, schema: dict,
                     schema_name: str = "out",
                     few_shot: list[dict] | None = None) -> dict:
    """Call OpenAI with structured JSON output + optional few-shot examples."""
    messages = [{"role": "system", "content": system}]
    if few_shot:
        for ex in few_shot:
            messages.append({"role": "user", "content": ex["user"]})
            messages.append({"role": "assistant", "content": ex["assistant"]})
    messages.append({"role": "user", "content": user})

    text_format = {
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
        }
    }
    try:
        resp = client.responses.create(
            model=MODEL,
            input=messages,
            text=text_format,
            store=False,
        )
        return json.loads(resp.output_text)
    except Exception:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
            store=False,
        )
        return json.loads(resp.choices[0].message.content)


# =====================================================================
# Step Coach
# =====================================================================

def evaluate_step(
    archetype_key: str,
    step_id: str,
    prompt_text: str,
    user_answer: str,
    conversation_so_far: list[dict],
) -> dict:
    """Evaluate a single step answer and return coaching feedback."""
    arch = get_archetype(archetype_key)
    step = next((s for s in arch.steps if s.id == step_id), None)
    if not step:
        return {
            "step_complete": False, "missing_points": ["Invalid step"],
            "one_best_nudge": "", "human_marker_suggestion": "",
            "next_step_id": "", "signpost_step_hint": "",
        }

    step_ids = [s.id for s in arch.steps]
    idx = step_ids.index(step_id)
    next_id = step_ids[idx + 1] if idx + 1 < len(step_ids) else "DONE"

    history_text = "\n".join(
        f"Step '{d['step']}': {d['answer']}" for d in conversation_so_far
    )
    framework_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(SIGNPOST_FRAMEWORK))

    system = f"""You are a blunt but helpful MMI (Multiple Mini Interview) coach. You are direct, specific, and encouraging.
You are evaluating ONE step of a guided practice station.

ARCHETYPE: {arch.name}
GOAL: {arch.goal}

CURRENT STEP: "{step.prompt}"
EVALUATION FOCUS: {step.coach_focus}

THE 7-STEP SIGNPOST FRAMEWORK (teach this to the candidate):
{framework_text}

HUMAN MARKERS (authentic sentence stems that make answers sound genuine):
{chr(10).join('- ' + m for m in arch.human_markers)}

COMMON TRAPS to watch for:
{chr(10).join('- ' + t for t in arch.common_traps)}

SCORING APPROACH:
- "step_complete" = true if the answer addresses the core of the step, even imperfectly.
- "missing_points" = specific things to add (max 3). Be concrete, not vague.
- "one_best_nudge" = a single coaching prompt. Frame it as a question or challenge.
- "human_marker_suggestion" = a sentence stem they could use (e.g., "I can imagine this person feels...")
- "signpost_step_hint" = which signpost framework step (1-7) is most relevant here and why.
- "next_step_id" = "{next_id}" if step is complete, or "{step_id}" if they need to retry.

STYLE RULES:
1. Be encouraging but honest - don't sugarcoat.
2. Never give the full answer - always nudge, never dump.
3. Use the signpost framework to guide improvement.
4. If the answer is reactive/judgmental, call it out directly.
5. If the answer lacks empathy, specifically suggest naming emotions."""

    user_msg = f"""MMI PROMPT: {prompt_text}

CONVERSATION SO FAR:
{history_text if history_text else "(This is the first step)"}

CURRENT STEP: {step.prompt}

USER'S ANSWER:
{user_answer}"""

    return _call_structured(system, user_msg, STEP_COACH_SCHEMA, "step_coach")


# =====================================================================
# Final Rubric  (all 40 coach examples as few-shot)
# =====================================================================

def generate_rubric(
    archetype_key: str,
    prompt_text: str,
    full_transcript: str,
    mode: str = "guided",
) -> dict:
    """Generate final rubric scores and feedback for a complete station attempt."""
    arch = get_archetype(archetype_key)
    framework_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(SIGNPOST_FRAMEWORK))

    system = f"""You are a blunt but helpful MMI coach. Score and coach the candidate's answer.
You provide brutally honest but constructive feedback.

ARCHETYPE: {arch.name}
GOAL: {arch.goal}
MODE: {mode}

=== DUAL SCORING SYSTEM ===

GRANULAR RUBRIC (0-2 each - used for quick coaching):
  structure: 0=no structure, 1=some structure, 2=clear framework used
  empathy: 0=no empathy/judgmental, 1=some empathy, 2=names emotions + validates
  information_gathering: 0=jumps to conclusions, 1=some info gathering, 2=asks clarifying questions + considers missing facts
  reasoning: 0=one-sided, 1=sees some nuance, 2=multi-perspective with principles
  professionalism: 0=unprofessional, 1=adequate, 2=mature + tactful

DETAILED RUBRIC (0-5 each - used for skill tracking):
  structure: Logical flow, uses appropriate framework, covers key steps
  empathy: Names emotions (own + others'), validates feelings, shows compassion
  perspective: Considers multiple stakeholders, acknowledges conflicting views
  reasoning: Identifies core tension, weighs tradeoffs, justifies with ethical principles
  actionability: Clear plan, specific steps, follow-up/escalation, practical
  clarity: Concise communication, appropriate tone, no jargon, easy to follow

OVERALL SCORE (0-10): A single holistic score where:
  0-3 = Reactive, judgmental, one-sided
  4-5 = Shows awareness but lacks depth/structure
  6-7 = Solid - covers most bases with some gaps
  8-9 = Strong - structured, empathetic, multi-perspective
  10 = Exemplary - could be used as a model answer

=== THE 7-STEP SIGNPOST FRAMEWORK ===
{framework_text}

=== WHAT TO INCLUDE ===
- "what_worked": tags like ["recap", "empathy", "if/then", "solutions", "summary"]. Empty if nothing stood out.
- "what_to_improve": tags like ["judgmental", "one-sided solution", "premature conclusion", "insufficient structure"]. Empty if excellent.
- "top_3_improvements": specific, actionable tips (not generic platitudes).
- "best_line_you_said": quote their best line verbatim, or "N/A" if nothing stood out.
- "rewrite_30s": a model 30-second answer hitting key points.
- "rewrite_90s": a model 90-second answer with depth, human markers, and the signpost framework.
- "recommended_signpost_framework": always include the 7 signpost steps.
- "micro_upgrade": For weak answers (score < 6): "Recap the scenario in 1 sentence | Name stakeholders + concerns | Ask 1-2 clarifying questions | Offer 2 options with pros/cons | State your recommendation + next step"
  For strong answers (score >= 6): "To push from strong to exceptional: add one clarifying question, mention one potential unintended consequence, and end with a crisp closing sentence."
- "interviewer_followups": 2-4 probing follow-up questions.

HUMAN MARKERS the candidate should ideally use:
{chr(10).join('- ' + m for m in arch.human_markers)}

STYLE: Be direct. If the answer is bad, say so. If it's great, celebrate it. No hedging."""

    user_msg = f"""MMI PROMPT: {prompt_text}

CANDIDATE'S FULL RESPONSE:
{full_transcript}"""

    # Feed ALL 40 coach examples so the model knows exactly the scoring voice
    return _call_structured(system, user_msg, FINAL_RUBRIC_SCHEMA, "final_rubric",
                            few_shot=COACH_EXAMPLES)


# =====================================================================
# Question Generator  (all 20 question-writer examples as few-shot)
# =====================================================================

QUESTION_GEN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "prompt_text": {"type": "string"},
        "themes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["prompt_text", "themes"],
}


def generate_question(archetype_key: str, difficulty: int = 3, themes: str = "") -> dict:
    """Generate a new MMI question using AI, with all question-writer examples as context."""
    arch = get_archetype(archetype_key)

    type_map = {
        "ethical_dilemma": "scenario",
        "roleplay": "acting",
        "teamwork": "scenario",
        "policy": "policy",
        "personal": "personal",
        "prioritization": "scenario",
        "cultural_humility": "scenario",
        "consent_capacity": "scenario",
        "interprofessional": "acting",
        "reflection": "personal",
    }
    station_type = type_map.get(archetype_key, "scenario")

    system = """You write high-quality MMI station prompts for medical school interview practice.
Your prompts should be:
- Realistic and vivid with specific details
- Have a clear ethical tension or decision point
- End with a clear question or directive for the candidate
- Be 100-250 words long
- Include diverse scenarios (healthcare, academic, workplace, social)

Return JSON with "prompt_text" and "themes" array."""

    theme_str = themes if themes else arch.goal
    user_msg = f"""Write one {station_type} MMI station prompt.
Theme(s): {theme_str}
Difficulty: {"easy" if difficulty <= 2 else "medium" if difficulty <= 3 else "hard"}
Archetype: {arch.name} - {arch.goal}
Style: realistic, concise but vivid, clear ask at the end.
Generate a fresh, original prompt."""

    # Feed ALL 20 question-writer examples for consistent MMI voice
    return _call_structured(system, user_msg, QUESTION_GEN_SCHEMA, "question_gen",
                            few_shot=QUESTION_WRITER_EXAMPLES)


# =====================================================================
# Question Extractor  (PDF ingestion)
# =====================================================================

def extract_question_from_chunk(chunk: str) -> dict:
    """Analyze a text chunk to see if it contains an MMI question."""
    system = """You are an expert at identifying MMI (Multiple Mini Interview) practice questions.
Analyze the given text chunk and determine:
1. Is this actually an MMI question/prompt? (not just informational text)
2. What archetype does it best fit? (ethical_dilemma, roleplay, teamwork, policy, personal, prioritization, cultural_humility, consent_capacity, interprofessional, reflection)
3. Clean up the prompt text (remove formatting artifacts, page numbers, make it a clear question)
4. Tag it with relevant themes.

Only set is_question=true if it's genuinely a practice prompt a student should answer."""

    return _call_structured(system, chunk, QUESTION_EXTRACTOR_SCHEMA, "question_extractor")


# =====================================================================
# Difficulty Mutator
# =====================================================================

def mutate_difficulty(prompt_text: str, current_difficulty: int, target_difficulty: int) -> dict:
    """Mutate a question to a different difficulty level while preserving core tension."""
    system = f"""You are an MMI question designer. Your job is to modify a question's difficulty.

DIFFICULTY SCALE:
D1: Short, clean prompt - one clear issue
D2: Add 1 distractor fact or complication
D3: Multiple stakeholders with conflicting incentives
D4: Ambiguity + emotional intensity + time pressure
D5: Add legal/policy constraints + reputational consequences

CURRENT DIFFICULTY: D{current_difficulty}
TARGET DIFFICULTY: D{target_difficulty}

CRITICAL RULE: The core ethical tension must be PRESERVED. You're adding/removing complexity, not changing the dilemma.

Return the mutated prompt and brief notes on what changed."""

    user_msg = f"Original prompt (D{current_difficulty}):\n{prompt_text}\n\nMutate to D{target_difficulty}."

    return _call_structured(system, user_msg, MUTATED_PROMPT_SCHEMA, "mutated_prompt")


# =====================================================================
# Interviewer Follow-ups
# =====================================================================

def generate_followups(archetype_key: str, prompt_text: str, user_answer: str) -> list[str]:
    """Generate probing follow-up questions like a real interviewer would."""
    arch = get_archetype(archetype_key)

    system = f"""You are an MMI interviewer conducting a follow-up after a candidate's initial response.
ARCHETYPE: {arch.name}

Generate 2-4 probing follow-up questions that:
1. Test depth of reasoning (e.g., "What if the patient refused?")
2. Challenge assumptions (e.g., "How do you know that's the right approach?")
3. Explore edge cases (e.g., "What if this happened in a different cultural context?")
4. Check emotional intelligence (e.g., "How would that make you feel?")

Return as a JSON object with a "followups" array of strings."""

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "followups": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["followups"],
    }

    result = _call_structured(system,
                              f"Prompt: {prompt_text}\n\nCandidate response: {user_answer}",
                              schema, "followups")
    return result.get("followups", [])


# =====================================================================
# Model Answer Generator  (DPO preferred examples as few-shot)
# =====================================================================

def generate_model_answer(prompt_text: str, time_limit: str = "90s") -> str:
    """Generate a high-quality model MMI answer using DPO preferred-answer examples."""
    system = """You are a medical school applicant answering an MMI station.
You are authentic, ethical, and structured. Do not include meta-commentary.

Follow this structure in your answer:
1. Briefly recap the scenario to show understanding
2. Identify the key stakeholders and their perspectives
3. Acknowledge emotions - yours and others'
4. Name the ethical principles at play (autonomy, beneficence, fairness, etc.)
5. Present at least 2 options with tradeoffs
6. State your recommendation with clear next steps
7. If appropriate, mention what you'd do if circumstances changed (if/then)

KEY QUALITIES OF A STRONG ANSWER:
- Non-judgmental - assume positive intent, don't jump to conclusions
- Empathetic - name specific emotions people might feel
- Multi-perspective - consider all stakeholders
- Practical - include specific, actionable steps
- Honest - own mistakes, accept responsibility
- Collaborative - prefer working together over unilateral action
- Proportional - match your response to the severity of the situation"""

    if time_limit == "30s":
        length_guide = "Keep your answer to about 30 seconds of speaking time (3-4 sentences)."
    else:
        length_guide = "Give a thorough answer of about 90 seconds of speaking time (8-12 sentences)."

    user_msg = f"""{prompt_text}

{length_guide}"""

    # Build messages with ALL 20 DPO preferred answers as examples
    messages = [{"role": "system", "content": system}]
    for ex in DPO_PREFERRED_EXAMPLES:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})
    messages.append({"role": "user", "content": user_msg})

    try:
        resp = client.responses.create(
            model=MODEL,
            input=messages,
            store=False,
        )
        return resp.output_text
    except Exception:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            store=False,
        )
        return resp.choices[0].message.content
