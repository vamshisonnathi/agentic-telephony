"""
Autonomous Phone & Telephony Specialist Agent.
Pre-configured agent persona equipped with phone calling, call status tracking,
and call termination tools adhering to the 4-Pillar Human Transaction Protocol.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
from agentic_telephony.tools.calling_tools import (
    PlaceOutboundCallTool,
    CheckCallStatusTool,
    EndCallTool,
)

# Optional CrewAI support
try:
    from crewai import Agent
    _CREWAI_AVAILABLE = True
except ImportError:
    _CREWAI_AVAILABLE = False
    Agent = object  # type: ignore


class PhoneCallingAgent:
    """Specialist agent for autonomous phone errands, inquiries, and appointments."""

    def __init__(self, name: str = "PhoneCallingAgent", caller_name: str = "Alex"):
        self.name = name
        self.caller_name = caller_name
        self.role = "Autonomous Telephony & Local Errand Specialist"
        self.goal = (
            "Dial businesses or contacts via Vapi/Retell AI, conduct natural human-like phone conversations "
            "without robotic phrasing, verify item availability and pricing, and report concise call outcomes and transcripts."
        )
        self.backstory = (
            f"You are an elite, articulate executive phone operator and concierge speaking as {caller_name}. "
            "You place real outbound phone calls to handle everyday errands such as checking inventory, "
            "ordering food for pickup, or scheduling appointments. "
            "You strictly adhere to human conversation rules: opening with a simple 'Hi.', "
            "asking direct short questions, using pronouns instead of repeating full item descriptions, "
            "speaking concisely without robotic jargon, and closing with practical logistics before hanging up."
        )
        self.tools = [
            PlaceOutboundCallTool(),
            CheckCallStatusTool(),
            EndCallTool(),
        ]

    def as_crewai_agent(self) -> Any:
        """Instantiates this agent as an official CrewAI Agent if crewai is installed."""
        if not _CREWAI_AVAILABLE:
            raise ImportError("crewai is not installed. Install it with: pip install crewai")
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            tools=self.tools,
            verbose=True,
        )


phone_calling_agent = PhoneCallingAgent()
