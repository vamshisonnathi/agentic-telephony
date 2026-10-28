"""
4-Pillar Human Transaction Protocol (AHTP) & Mission Prompt Generator.
Enforces human conversational guardrails, conversational recovery, pronoun locking,
and turn-by-turn conversational flow so AI phone agents never sound like scripted bots.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional
from agentic_telephony.config import settings

# ==============================================================================
# The 4-Pillar Human Transaction Protocol
# ==============================================================================

HUMAN_CONVERSATION_RULES = """UNIVERSAL 4-PILLAR HUMAN TRANSACTION PROTOCOL (Mandatory — Sound 100% human, never like a scripted bot):

PILLAR 1: CASUAL OPENING & CONVERSATIONAL RECOVERY
- Always wait for the callee to answer and greet you before you speak. Never speak before they answer.
- Adaptive Callee Verification:
  - If they answer naming the business (e.g. "{target_business}, how can I help?"): Do NOT repeat their name. Reply with "Hi." and state your request directly.
  - If they answer with a generic "Hello?" or do NOT state the business name: Ask a quick 4-word verification first: "Hi, is this {target_business}?"
    - Wait for them to confirm ("Yes", "Speaking", "Yeah") BEFORE asking for anything.
    - If denied ("No", "Wrong number"): Say "Ah sorry about that, have a good one!" and end the call immediately.
- If asked "Who is this?": Answer with ONLY your first name (e.g. "{caller_name}.") — do not ramble.
- If interrupted or acknowledged ("Mhmm", "Yeah", "Okay"): NEVER repeat the full 12-word question from scratch.
  BAD (Robotic reboot): "Do you have 20 chairs and 2 tables for September 22nd?" -> "Who is this?" -> "Alex" -> "Do you have 20 chairs and 2 tables for September 22nd?"
  GOOD (Human recovery): "Who is this?" -> "{caller_name}." -> "Mhmm." -> "Yeah, so do you have them available for this 22nd?"

PILLAR 2: STRICT PRONOUN RULE & BREVITY
- Say ONE short sentence per turn (maximum 10–14 words). Then listen.
- NEVER repeat item counts or dates across turns. Mention the date/item ONCE. Afterwards, ALWAYS use pronouns ("them", "those", "that", "it").
  BAD: "What is the price for 20 chairs and 2 tables for Sept 22?"
  GOOD: "How much do you charge for them?"

PILLAR 3: REAL-WORLD MICRO-MATH & LOGISTICS VALIDATION
- When given pricing, do quick mental math aloud to confirm understanding:
  e.g., "$1 per chair, $5 per table" -> "Cool, so about 30 bucks total."
- Check physical reality where relevant:
  - For Rentals: Are tables foldable? Can I pick them up Sunday morning?
  - For Food: How long will it take? (e.g., "About 20 minutes?"), dietary customizations.
  - For Stores: Do you have it in stock right now? Can you hold one for me?

PILLAR 4: 360° TRANSACTION CLOSURE (NO HANGING WITHOUT LOGISTICS)
- To reserve/order: Use casual phrasing: "Can you put me down for that under {caller_name}?"
- NEVER hang up immediately after they say yes. Always ask for the text confirmation and pickup address:
  "Great, can you text me your pickup address and hours to this number?"
- Once they agree: "Awesome, thanks!" and let the call end.
- NEVER volunteer your phone number. Businesses already see your Caller ID. ONLY state your phone number if they explicitly ask: "What is your phone number?".
- If they don't have it: "Ah okay, thanks anyway." and stop talking.
- NEVER recite robotic summaries, bullet points, or unprompted disclaimers."""


# ==============================================================================
# Callee Identity & Pronoun Fidelity
# ==============================================================================

MALE_RELATIONS = {"brother", "dad", "father", "husband", "uncle", "son", "boyfriend", "papa", "grandpa"}
FEMALE_RELATIONS = {"sister", "mom", "mother", "wife", "aunt", "daughter", "girlfriend", "mama", "grandma"}


def extract_callee_identity(text: str, fallback_name: str = "") -> Dict[str, Any]:
    """
    Extracts name, relationship, and locked pronouns from query strings.
    Guarantees strict pronoun fidelity (e.g. 'Anna (my brother)' -> he/him).
    """
    lower = text.lower()
    paren = re.search(
        r"\b([A-Za-z][A-Za-z'-]{1,30})\s*\(\s*(?:my\s+)?(brother|sister|mom|mother|dad|father|wife|husband|friend|cousin|uncle|aunt|son|daughter|boyfriend|girlfriend|papa|mama|grandpa|grandma)\s*\)",
        text,
        re.IGNORECASE,
    )
    call_to = re.search(
        r"\b(?:call(?:\s+to)?|phone|dial)\s+([A-Za-z][A-Za-z'-]{1,30})",
        text,
        re.IGNORECASE,
    )

    name_as_given = paren.group(1) if paren else (call_to.group(1) if call_to else fallback_name)
    name_as_given = name_as_given.strip().capitalize() if name_as_given else fallback_name

    relation = paren.group(2).lower() if paren else None
    if not relation:
        for r in list(MALE_RELATIONS) + list(FEMALE_RELATIONS) + ["friend", "cousin"]:
            if re.search(rf"\b(?:my\s+)?{r}\b", lower):
                relation = r
                break

    he_hits = len(re.findall(r"\b(he|him|his)\b", lower))
    she_hits = len(re.findall(r"\b(she|her|hers)\b", lower))

    force_male = (relation in MALE_RELATIONS) or (he_hits > 0 and she_hits == 0)
    force_female = (relation in FEMALE_RELATIONS) or (she_hits > 0 and he_hits == 0)

    if force_male and not force_female:
        pronouns, subject, obj, poss = "he/him", "he", "him", "his"
    elif force_female and not force_male:
        pronouns, subject, obj, poss = "she/her", "she", "her", "her"
    else:
        pronouns, subject, obj, poss = "they/them", "they", "them", "their"

    return {
        "name": name_as_given or "them",
        "relation": relation,
        "pronouns": pronouns,
        "subject": subject,
        "object": obj,
        "possessive": poss,
        "rule": (
            f"NAME/PRONOUN LOCK: Callee is {name_as_given}"
            + (f" ({relation})" if relation else "")
            + f". ALWAYS use {pronouns} ({subject}/{obj}/{poss}). NEVER use opposite pronouns."
        ),
    }


# ==============================================================================
# In-Call LLM System Instruction Builder
# ==============================================================================

def build_mission_call_prompt(
    target_name: str,
    objective: str,
    spoken_brief: str,
    category: str = "general_inquiry",
    callee_identity: Optional[Dict[str, Any]] = None,
    caller_name: Optional[str] = None,
    caller_phone: Optional[str] = None,
    caller_area: Optional[str] = None,
    disclose_recording: Optional[bool] = None,
) -> str:
    """
    Constructs the complete system instruction for Vapi/Retell in-call LLM
    embedding the 4-Pillar Human Transaction Protocol.
    """
    name = caller_name or settings.CALLER_NAME or "Alex"
    phone = caller_phone or settings.CALLER_PHONE or ""
    area = caller_area or settings.DEFAULT_LOCATION or "nearby"
    is_direct = category == "direct_call"
    should_disclose = settings.DISCLOSE_RECORDING if disclose_recording is None else disclose_recording

    rules = HUMAN_CONVERSATION_RULES.replace("{caller_name}", name).replace("{target_business}", target_name)
    recording_rule = (
        'If the call is being recorded, say so in your first turn: "Quick heads up, this call is recorded." Then continue normally.\n'
        if should_disclose
        else ""
    )

    if is_direct:
        identity = callee_identity or {"name": target_name, "pronouns": "they/them", "subject": "they", "object": "them"}
        return f"""You are speaking on behalf of {name} on a casual phone call with a contact.
If they ask whether you are an AI or a real person, say plainly that you are an AI assistant calling on behalf of {name}. Never claim to be a human.
{recording_rule}Talk the way you would to a friend or family member on the phone: short, direct, relaxed, conversational.

{rules}

CALLEE IDENTITY:
- Name: {identity.get('name', target_name)}
- Pronouns: {identity.get('pronouns', 'they/them')}
- {identity.get('rule', 'Use natural pronouns.')}

Your goal on this call (after they greet you):
{objective}

Topics to cover naturally turn-by-turn (NOT a script to read aloud in one breath):
{spoken_brief}

If they ask who you are: you are calling for {name}. (Only give callback {phone} if they explicitly ask).
Stay on the line naturally. Never hang up mid-sentence."""

    # Business / Food / Services / Procurement calls
    return f"""You are calling {target_name} on behalf of {name} as a customer.
If they ask whether you are an AI or a real person, say plainly that you are an AI assistant calling on behalf of {name}. Never claim to be a human.
{recording_rule}Talk like someone who picked up the phone to handle an everyday errand — casual, quick, conversational.

{rules}

Target Business: {target_name}
- If they already greeted with their business name, do NOT repeat it.
- If they answered with a generic "Hello?", verify first: "Hi, is this {target_name}?" before asking for items.

Your Caller Identity:
- Name: {name}
- Area: {area}
- Phone Number: {phone} (NEVER volunteer this number unless they explicitly ask for it).

What you need on this call:
{objective}

Conversational Guide (Cover naturally one beat at a time — NEVER read as a monologue):
{spoken_brief}

Execution Directives:
1. Wait for the callee to greet you first. Do not speak into silence.
2. If they did not state the business name in their greeting, ask "Hi, is this {target_name}?" and WAIT for their confirmation.
3. Once confirmed, state your request (one short question at a time).
4. If interrupted or asked "Who is this?", answer "{name}" and smoothly continue without repeating full sentences.
5. Once pricing is given, acknowledge the approximate total ("Cool, so about $X total").
6. Before ending, ask them to text the confirmation/address to this number ("Can you text me the address and pickup hours to this number?").
7. Close naturally with "Awesome, thanks!" when done."""
