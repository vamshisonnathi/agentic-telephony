"""
Agentic Telephony
=================
Autonomous Human-like AI Phone Calling & Receiving Agent framework powered by
Vapi AI & Retell AI with the 4-Pillar Human Transaction Protocol (AHTP).
"""

from agentic_telephony.config import settings, TelephonySettings
from agentic_telephony.engine import TelephonyEngine, telephony_engine
from agentic_telephony.tracker import CallStateTracker, call_tracker
from agentic_telephony.protocol import (
    HUMAN_CONVERSATION_RULES,
    build_mission_call_prompt,
    extract_callee_identity,
)
from agentic_telephony.providers.base import BaseTelephonyProvider
from agentic_telephony.providers.vapi import VapiProvider
from agentic_telephony.providers.retell import RetellProvider
from agentic_telephony.tools.calling_tools import (
    PlaceOutboundCallTool,
    CheckCallStatusTool,
    EndCallTool,
)
from agentic_telephony.tools.resolver import to_e164_us
from agentic_telephony.agent import PhoneCallingAgent, phone_calling_agent

try:
    from agentic_telephony.server.app import create_app, app
except Exception:
    create_app = None
    app = None

__version__ = "1.0.0"

__all__ = [
    "settings",
    "TelephonySettings",
    "TelephonyEngine",
    "telephony_engine",
    "CallStateTracker",
    "call_tracker",
    "HUMAN_CONVERSATION_RULES",
    "build_mission_call_prompt",
    "extract_callee_identity",
    "BaseTelephonyProvider",
    "VapiProvider",
    "RetellProvider",
    "PlaceOutboundCallTool",
    "CheckCallStatusTool",
    "EndCallTool",
    "to_e164_us",
    "PhoneCallingAgent",
    "phone_calling_agent",
    "create_app",
    "app",
]
