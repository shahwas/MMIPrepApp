"""
Station archetypes with step-ladder prompts, human markers, and common traps.
Each archetype defines the tutor's coaching scaffold.
"""

from dataclasses import dataclass, field


@dataclass
class Step:
    id: str
    prompt: str
    coach_focus: str  # what the LLM should evaluate in user's answer


@dataclass
class Archetype:
    key: str
    name: str
    goal: str
    steps: list[Step]
    human_markers: list[str]
    common_traps: list[str]
    skill_weights: dict[str, float]  # which skills this archetype emphasizes


ARCHETYPES: dict[str, Archetype] = {}

# ─── A) Ethical Dilemma / Professionalism ────────────────────────
ARCHETYPES["ethical_dilemma"] = Archetype(
    key="ethical_dilemma",
    name="Ethical Dilemma / Professionalism",
    goal="Balanced reasoning + defensible action + empathy.",
    steps=[
        Step("tension", "What's the core tension? What values or principles are in conflict here?",
             "Identifies ≥2 competing values (e.g. autonomy vs beneficence, honesty vs loyalty)"),
        Step("facts", "What facts do you need, and what assumptions are you making?",
             "Distinguishes known facts from assumptions; identifies ≥1 key unknown"),
        Step("stakeholders", "Who are the stakeholders? What might each one feel or need — including you?",
             "Names ≥3 stakeholders with emotions/needs; includes self"),
        Step("options", "What are 2–3 realistic options? What are the pros and cons of each?",
             "Gives ≥2 options with genuine tradeoffs, not strawmen"),
        Step("recommend", "What's your recommended action and why?",
             "Clear recommendation with ethical justification; acknowledges limitations"),
        Step("communicate", "How would you communicate this? Think about tone, wording, and de-escalation.",
             "Shows empathetic communication plan; appropriate language"),
        Step("followup", "What about escalation, documentation, or follow-up?",
             "Identifies reporting/documentation needs; shows systems thinking"),
    ],
    human_markers=[
        "I'd feel torn because…",
        "I can see why they'd feel ___; I'd want to acknowledge that before problem-solving.",
        "I don't have all the facts yet, so I'd first clarify…",
        "The strongest argument against my position is…",
        "Even if I disagree, I'd want to understand their perspective by…",
    ],
    common_traps=[
        "Jumping to a solution without exploring the tension",
        "Ignoring your own emotions or the emotional impact on others",
        "Presenting one option as obviously correct (no real tradeoff)",
        "Forgetting documentation/escalation/follow-up",
        "Being preachy or judgmental instead of balanced",
    ],
    skill_weights={"structure": 1.0, "empathy": 1.2, "perspective": 1.2, "reasoning": 1.3, "actionability": 1.0, "clarity": 0.8},
)

# ─── B) Role-Play / Difficult Conversation ──────────────────────
ARCHETYPES["roleplay"] = Archetype(
    key="roleplay",
    name="Role-Play / Difficult Conversation",
    goal="De-escalation + empathy + collaborative plan.",
    steps=[
        Step("open", "Introduce your role and set your intention. (e.g., 'I'm here to help.')",
             "Warm opening; identifies self; states willingness to help"),
        Step("acknowledge", "Acknowledge the person's emotion. Name it and validate it.",
             "Names specific emotion; validates without dismissing"),
        Step("clarify", "Ask 1–2 targeted questions to understand the situation better.",
             "Asks open-ended, non-judgmental clarifying questions"),
        Step("explain", "Explain the situation or options in concise, non-jargony language.",
             "Clear, accessible explanation; avoids medical/technical jargon"),
        Step("collaborate", "Ask: 'What matters most to you right now?' Explore shared goals.",
             "Invites patient/person into decision-making; shows respect for autonomy"),
        Step("close", "Summarize what you'll do, the next step, and a safety net.",
             "Clear action plan; follow-up commitment; safety net statement"),
    ],
    human_markers=[
        "I can hear how frustrating/scary this is.",
        "If I'm understanding you correctly…",
        "Here's what I can do right now, and here's what I'll escalate.",
        "That sounds really difficult. Thank you for sharing that with me.",
        "I want to make sure we're on the same page…",
    ],
    common_traps=[
        "Jumping to problem-solving before acknowledging emotions",
        "Using jargon or being condescending",
        "Being defensive or dismissive of complaints",
        "Not asking what matters to the person",
        "Ending without a clear plan or safety net",
    ],
    skill_weights={"structure": 0.8, "empathy": 1.5, "perspective": 1.0, "reasoning": 0.7, "actionability": 1.0, "clarity": 1.3},
)

# ─── C) Teamwork / Conflict Resolution ──────────────────────────
ARCHETYPES["teamwork"] = Archetype(
    key="teamwork",
    name="Teamwork / Conflict Resolution",
    goal="Diagnose team dynamics + take accountable action.",
    steps=[
        Step("goal", "What's the team goal, and what's currently failing or at risk?",
             "Identifies shared objective and specific breakdown"),
        Step("role", "What's your role and responsibility in this situation?",
             "Shows ownership without over-stepping; clarifies boundaries"),
        Step("feelings", "What might each person be experiencing or feeling?",
             "Shows perspective-taking for ≥2 team members"),
        Step("options", "What are your options? (e.g., private 1:1, reset expectations, redistribute tasks, escalate)",
             "Generates ≥2 concrete options appropriate to the situation"),
        Step("approach", "Pick your approach. What exact words would you use?",
             "Specific, respectful language; shows communication skill"),
        Step("prevent", "How would you prevent this from recurring? (process change)",
             "Systems thinking; proposes sustainable fix, not just a band-aid"),
    ],
    human_markers=[
        "I'd want to talk to them privately first before assuming…",
        "My responsibility here is to…",
        "I imagine they might be feeling ___ because…",
        "I'd say something like: '…'",
        "To prevent this next time, I'd suggest…",
    ],
    common_traps=[
        "Blaming one person without exploring context",
        "Avoiding the conflict entirely (being too passive)",
        "Jumping to escalation without trying direct conversation first",
        "Not considering others' perspectives",
        "No concrete prevention strategy",
    ],
    skill_weights={"structure": 1.0, "empathy": 1.2, "perspective": 1.3, "reasoning": 0.9, "actionability": 1.2, "clarity": 1.0},
)

# ─── D) Policy / Public Health / Contemporary Issue ─────────────
ARCHETYPES["policy"] = Archetype(
    key="policy",
    name="Policy / Public Health / Contemporary Issue",
    goal="Structured analysis, tradeoffs, implementation.",
    steps=[
        Step("define", "Define the problem and a goal metric — what does 'success' look like?",
             "Clear problem statement; measurable or meaningful success criterion"),
        Step("stakeholders", "Who are the stakeholders, and what are the equity impacts?",
             "Names diverse stakeholders; considers vulnerable/marginalized groups"),
        Step("options", "Propose 2–3 policy options.",
             "Distinct, realistic policy options (not strawmen)"),
        Step("tradeoffs", "Analyze tradeoffs: ethics, feasibility, and unintended consequences.",
             "Balanced analysis; acknowledges uncertainty and unintended effects"),
        Step("recommend", "What's your recommendation and why?",
             "Justified recommendation; shows awareness of limitations"),
        Step("implement", "How would you implement and evaluate the policy?",
             "Practical implementation steps; evaluation/feedback mechanism"),
    ],
    human_markers=[
        "Success here would mean…",
        "The people most affected would be…",
        "An unintended consequence could be…",
        "I'd weigh ___ more heavily because…",
        "To evaluate whether it's working, I'd look at…",
    ],
    common_traps=[
        "Taking a rigid ideological stance without nuance",
        "Ignoring equity or vulnerable populations",
        "Proposing unrealistic or vague solutions",
        "Forgetting to evaluate outcomes",
        "Not acknowledging uncertainty",
    ],
    skill_weights={"structure": 1.3, "empathy": 0.8, "perspective": 1.2, "reasoning": 1.3, "actionability": 1.0, "clarity": 1.0},
)

# ─── E) Personal Motivation / Experience (STARR) ────────────────
ARCHETYPES["personal"] = Archetype(
    key="personal",
    name="Personal Motivation / Experience (STARR)",
    goal="Authentic story with reflection and growth.",
    steps=[
        Step("pick", "Pick an experience (take 10 seconds to think).",
             "Chooses a relevant, specific experience"),
        Step("situation", "Describe the Situation and Task — what was at stake?",
             "Clear context; explains why it mattered"),
        Step("action", "What Actions did you take? Be specific.",
             "Concrete actions (not vague 'I helped'); shows initiative"),
        Step("result", "What was the Result or impact?",
             "Tangible outcome; honest about both success and challenges"),
        Step("reflection", "Reflection: What did you learn? What would you do differently?",
             "Genuine self-awareness; growth mindset; connects to medicine/future"),
    ],
    human_markers=[
        "This mattered to me because…",
        "What I actually did was…",
        "Looking back, I'd do ___ differently because…",
        "This taught me that…",
        "I think this connects to medicine because…",
    ],
    common_traps=[
        "Being vague ('I helped people') instead of specific",
        "Hero narrative without acknowledging team or limitations",
        "No genuine reflection (just 'it went great')",
        "Picking an experience that's not relevant",
        "Not connecting the lesson to future growth",
    ],
    skill_weights={"structure": 1.0, "empathy": 1.0, "perspective": 0.8, "reasoning": 0.7, "actionability": 0.8, "clarity": 1.3},
)

# ─── F) Prioritization / Triage / Time-Pressure ─────────────────
ARCHETYPES["prioritization"] = Archetype(
    key="prioritization",
    name="Prioritization / Triage / Time-Pressure",
    goal="Clear triage logic under constraints.",
    steps=[
        Step("constraints", "What are the constraints? (time, resources, rules)",
             "Identifies key constraints; shows awareness of limits"),
        Step("criteria", "What triage criteria will you use? (urgency, harm, reversibility)",
             "Articulates clear prioritization framework"),
        Step("order", "What order would you address things in, and why?",
             "Logical ordering justified by criteria; not arbitrary"),
        Step("communicate", "How would you communicate your plan to stakeholders?",
             "Clear, calm communication; manages expectations"),
        Step("contingency", "What contingencies do you have if things change?",
             "Shows adaptability; backup plan; delegation awareness"),
    ],
    human_markers=[
        "The most urgent thing is ___ because…",
        "I'd prioritize based on…",
        "If the situation changes, I'd…",
        "I'd communicate to ___ by saying…",
        "The hardest tradeoff here is…",
    ],
    common_traps=[
        "Trying to do everything at once",
        "No clear criteria for prioritization",
        "Ignoring communication with stakeholders",
        "No backup plan",
        "Not justifying the order",
    ],
    skill_weights={"structure": 1.4, "empathy": 0.7, "perspective": 1.0, "reasoning": 1.2, "actionability": 1.3, "clarity": 1.0},
)

# ─── G) Cultural Humility / Disagreement with Care Plan ─────────
ARCHETYPES["cultural_humility"] = Archetype(
    key="cultural_humility",
    name="Cultural Humility / Disagreement with Care Plan",
    goal="Respect patient values while ensuring safety.",
    steps=[
        Step("acknowledge", "Acknowledge the person's values and avoid making assumptions.",
             "Shows cultural humility; avoids stereotyping; genuine curiosity"),
        Step("explore", "Explore their reasons with open questions.",
             "Asks why respectfully; seeks to understand, not to argue"),
        Step("explain", "Explain the medical context in plain, respectful language.",
             "Accessible explanation; no condescension; respects autonomy"),
        Step("shared", "What shared decision-making options exist?",
             "Offers choices; involves patient in decision; finds middle ground"),
        Step("boundaries", "Where are the safety/ethics boundaries?",
             "Knows when to draw lines (child safety, emergencies); explains why"),
        Step("support", "What support resources could help? (interpreter, social work, spiritual care)",
             "Practical resource awareness; shows systems knowledge"),
    ],
    human_markers=[
        "I wouldn't want to assume — I'd ask about…",
        "I respect that this is important to them because…",
        "In plain terms, the medical concern is…",
        "Could we find a middle ground where…",
        "If safety is at risk, I'd need to…",
        "I'd want to involve ___ to support them.",
    ],
    common_traps=[
        "Stereotyping or making cultural assumptions",
        "Being paternalistic ('doctor knows best')",
        "Ignoring the patient's autonomy",
        "Not knowing when safety overrides autonomy",
        "Forgetting to offer support resources",
    ],
    skill_weights={"structure": 0.8, "empathy": 1.4, "perspective": 1.3, "reasoning": 1.0, "actionability": 1.0, "clarity": 1.1},
)

# ─── H) Consent & Capacity ──────────────────────────────────────
ARCHETYPES["consent_capacity"] = Archetype(
    key="consent_capacity",
    name="Consent & Capacity",
    goal="Ensure informed consent while respecting autonomy.",
    steps=[
        Step("assess", "How would you assess this person's capacity to make this decision?",
             "Knows capacity criteria: understand, retain, weigh, communicate"),
        Step("inform", "What information does this person need to make an informed decision?",
             "Covers: diagnosis, options, risks/benefits, alternatives, doing nothing"),
        Step("voluntariness", "Is this decision free from coercion or undue influence?",
             "Considers pressure from family, institution, or circumstance"),
        Step("respect", "If they refuse, how do you respect that while ensuring safety?",
             "Balances autonomy with duty of care; knows when to escalate"),
        Step("document", "What would you document and who else needs to know?",
             "Proper documentation; involves team; follow-up plan"),
    ],
    human_markers=[
        "I'd want to make sure they understand by asking them to explain back…",
        "Even if I disagree, their right to decide is…",
        "I'd check if anyone is pressuring them by…",
        "I'd document this because…",
    ],
    common_traps=[
        "Assuming lack of capacity based on age, diagnosis, or decision",
        "Not checking understanding (just 'signing the form')",
        "Ignoring coercion from family members",
        "Not knowing when to involve substitute decision-maker",
    ],
    skill_weights={"structure": 1.1, "empathy": 1.2, "perspective": 1.0, "reasoning": 1.3, "actionability": 1.0, "clarity": 1.0},
)

# ─── I) Collaboration with Other Professionals ──────────────────
ARCHETYPES["interprofessional"] = Archetype(
    key="interprofessional",
    name="Interprofessional Collaboration",
    goal="Effective teamwork across professional boundaries.",
    steps=[
        Step("situation", "What's the situation and why does it require interprofessional input?",
             "Clear problem identification; recognizes need for collaboration"),
        Step("roles", "What does each professional bring — what's their expertise?",
             "Shows respect for other professions' scope and knowledge"),
        Step("communicate", "How would you communicate — using what format? (e.g., SBAR)",
             "Uses structured communication; appropriate medium"),
        Step("conflict", "What if you disagree with another professional's recommendation?",
             "Respectful disagreement; patient safety focus; escalation awareness"),
        Step("plan", "What's the shared plan and how do you follow up?",
             "Clear shared plan; defined responsibilities; follow-up mechanism"),
    ],
    human_markers=[
        "I'd value their expertise in ___ because…",
        "I'd use SBAR to communicate: Situation, Background, Assessment, Recommendation",
        "If we disagreed, I'd say something like…",
        "The patient's interest comes first, so…",
    ],
    common_traps=[
        "Assuming you know best (hierarchy mindset)",
        "Not using structured communication",
        "Ignoring input from nurses, social workers, etc.",
        "No clear follow-up plan",
    ],
    skill_weights={"structure": 1.1, "empathy": 0.9, "perspective": 1.2, "reasoning": 1.0, "actionability": 1.2, "clarity": 1.2},
)

# ─── J) Reflection / Self-Awareness ─────────────────────────────
ARCHETYPES["reflection"] = Archetype(
    key="reflection",
    name="Reflection / Self-Awareness",
    goal="Honest self-assessment with growth orientation.",
    steps=[
        Step("identify", "What's the situation or quality you're being asked to reflect on?",
             "Understands the reflection prompt; identifies the core theme"),
        Step("honest", "Be honest: what did you do well and where did you fall short?",
             "Genuine honesty; avoids humble-bragging or excessive self-criticism"),
        Step("impact", "What was the impact of your actions on others?",
             "Shows awareness of effect on others; takes responsibility"),
        Step("learn", "What did you learn from this experience?",
             "Specific lesson, not generic; shows genuine insight"),
        Step("forward", "What will you do differently going forward?",
             "Concrete, actionable change; growth mindset"),
    ],
    human_markers=[
        "Honestly, I could have done ___ better.",
        "The impact on others was…",
        "What I learned is…",
        "Going forward, I'll change ___ by…",
        "I'm still working on…",
    ],
    common_traps=[
        "Humble-bragging instead of genuine reflection",
        "Being too vague ('I learned a lot')",
        "Not acknowledging impact on others",
        "No concrete plan for improvement",
        "Being overly self-critical without showing growth",
    ],
    skill_weights={"structure": 0.9, "empathy": 1.1, "perspective": 1.0, "reasoning": 0.8, "actionability": 1.0, "clarity": 1.2},
)


def get_archetype(key: str) -> Archetype:
    return ARCHETYPES[key]


def get_archetype_names() -> dict[str, str]:
    return {k: v.name for k, v in ARCHETYPES.items()}


def get_step_by_id(archetype_key: str, step_id: str) -> Step | None:
    arch = ARCHETYPES.get(archetype_key)
    if not arch:
        return None
    for s in arch.steps:
        if s.id == step_id:
            return s
    return None
