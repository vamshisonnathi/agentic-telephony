"""
Autonomous Phone Calling Tools for AI Agents (CrewAI / LangChain / Standalone).
Equips agents with capabilities to dial real phone numbers, monitor live call transcripts,
and terminate active calls.
"""

from __future__ import annotations

import time
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, Field

from agentic_telephony.protocol import extract_callee_identity

# Gracefully support CrewAI BaseTool if installed; otherwise fallback to basic class
try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:  # type: ignore
        name: str = ""
        description: str = ""
        args_schema: Optional[Type[BaseModel]] = None


# ==============================================================================
# Tool 1: Place Outbound Call
# ==============================================================================

class PlaceOutboundCallInput(BaseModel):
    phone_number: str = Field(..., description="E.164 phone number to dial (e.g. '+15551234567')")
    target_name: str = Field(..., description="Name of the recipient or business (e.g. 'Luigi\'s Pizza', 'Dr. Smith', 'Mom')")
    objective: str = Field(..., description="Concrete goal of the call (e.g. 'Ask if they have gluten-free crust and prices')")
    spoken_brief: str = Field(..., description="Conversational talking points covered turn-by-turn")
    category: str = Field(default="general_inquiry", description="'general_inquiry' for businesses or 'direct_call' for contacts")
    provider: Optional[str] = Field(default=None, description="Optional override: 'vapi' or 'retell'")


class PlaceOutboundCallTool(BaseTool):
    name: str = "place_outbound_phone_call"
    description: str = (
        "Dispatches an autonomous, natural human-sounding phone call via Vapi AI or Retell AI. "
        "Strictly enforces the 4-Pillar Human Transaction Protocol so the bot never sounds robotic or scripted."
    )
    args_schema: Type[BaseModel] = PlaceOutboundCallInput

    def _run(
        self,
        phone_number: str,
        target_name: str,
        objective: str,
        spoken_brief: str,
        category: str = "general_inquiry",
        provider: Optional[str] = None,
    ) -> str:
        from agentic_telephony.engine import telephony_engine

        callee_identity = extract_callee_identity(f"{target_name} {objective}", fallback_name=target_name)

        try:
            res = telephony_engine.place_call(
                phone_number=phone_number,
                target_name=target_name,
                objective=objective,
                spoken_brief=spoken_brief,
                category=category,
                callee_identity=callee_identity,
                provider=provider,
            )
            call_id = res.get("call_id")
            engine_name = res.get("provider", "Telephony").upper()
            return (
                f"📞 Call initiated via {engine_name}!\n"
                f"- Call ID: {call_id}\n"
                f"- Dialing: {target_name} ({phone_number})\n"
                f"- Goal: {objective}\n"
                f"- Status: {res.get('status', 'in-progress')}\n"
                f"You can monitor live call status with 'check_phone_call_status(call_id=\"{call_id}\")'."
            )
        except Exception as e:
            return f"❌ Failed to dispatch phone call to {target_name} ({phone_number}): {e}"

    def run(self, *args, **kwargs):
        return self._run(*args, **kwargs)


# ==============================================================================
# Tool 2: Check Call Status
# ==============================================================================

class CheckCallStatusInput(BaseModel):
    call_id: str = Field(..., description="Unique call ID returned when the call was placed")


class CheckCallStatusTool(BaseTool):
    name: str = "check_phone_call_status"
    description: str = "Checks the real-time status, live turn-by-turn transcript, and outcome of an active phone call."
    args_schema: Type[BaseModel] = CheckCallStatusInput

    def _run(self, call_id: str) -> str:
        from agentic_telephony.engine import telephony_engine

        info = telephony_engine.get_call_status(call_id)
        if not info:
            return f"⚠️ Call ID '{call_id}' not found in active call tracker."

        status = info.get("status", "unknown")
        target = info.get("target_name", "Unknown")
        transcript = info.get("transcript", "(No speech recorded yet)")
        summary = info.get("summary", "")
        ended_reason = info.get("ended_reason", "")

        out = [
            f"📞 Call Status for '{target}' [ID: {call_id}]:",
            f"- Status: {status.upper()}",
        ]
        if ended_reason:
            out.append(f"- Ended Reason: {ended_reason}")
        if summary:
            out.append(f"- Summary: {summary}")
        out.append(f"- Live Transcript:\n{transcript}")

        return "\n".join(out)

    def run(self, *args, **kwargs):
        return self._run(*args, **kwargs)


# ==============================================================================
# Tool 3: End Call
# ==============================================================================

class EndCallInput(BaseModel):
    call_id: str = Field(..., description="Call ID of the active call to terminate")


class EndCallTool(BaseTool):
    name: str = "end_active_phone_call"
    description: str = "Immediately hangs up and terminates an ongoing phone call."
    args_schema: Type[BaseModel] = EndCallInput

    def _run(self, call_id: str) -> str:
        from agentic_telephony.engine import telephony_engine

        res = telephony_engine.end_call(call_id)
        return f"🛑 Call '{call_id}' termination requested. Status: {res.get('status', 'ended')}."

    def run(self, *args, **kwargs):
        return self._run(*args, **kwargs)
