"""
Retell AI Telephony Provider.
Communicates with Retell AI REST API (https://api.retellai.com) to initiate phone calls
and pass mission prompts, callee identities, and dynamic variables to Retell agents.
"""

from __future__ import annotations

import time
import requests
from typing import Optional, Dict, Any

from agentic_telephony.config import settings
from agentic_telephony.providers.base import BaseTelephonyProvider
from agentic_telephony.protocol import build_mission_call_prompt
from agentic_telephony.tracker import call_tracker
from agentic_telephony.tools.resolver import to_e164_us


class RetellProvider(BaseTelephonyProvider):
    """Client for Retell AI outbound calling and live call management."""

    BASE_URL = "https://api.retellai.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.api_key = api_key or settings.RETELL_API_KEY
        self.agent_id = agent_id or settings.RETELL_AGENT_ID
        self.from_number = from_number or settings.RETELL_FROM_NUMBER

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("RETELL_API_KEY is not configured. Set RETELL_API_KEY in .env or pass it to constructor.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def place_call(
        self,
        phone_number: str,
        target_name: str,
        objective: str,
        spoken_brief: str,
        category: str = "general_inquiry",
        callee_identity: Optional[Dict[str, Any]] = None,
        server_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches an autonomous outbound phone call via Retell AI."""
        if not self.from_number:
            raise ValueError("RETELL_FROM_NUMBER is not configured in .env (e.g. your purchased Retell phone number)")
        if not self.agent_id:
            raise ValueError("RETELL_AGENT_ID is not configured in .env (create an agent in Retell Dashboard)")

        e164_phone = to_e164_us(phone_number)
        if not e164_phone:
            raise ValueError(f"Invalid phone number provided: '{phone_number}'")

        system_prompt = build_mission_call_prompt(
            target_name=target_name,
            objective=objective,
            spoken_brief=spoken_brief,
            category=category,
            callee_identity=callee_identity,
            caller_name=settings.CALLER_NAME,
            caller_phone=settings.CALLER_PHONE,
            caller_area=settings.DEFAULT_LOCATION,
        )

        payload: Dict[str, Any] = {
            "from_number": self.from_number,
            "to_number": e164_phone,
            "override_agent_id": self.agent_id,
            "retell_llm_dynamic_variables": {
                "caller_name": settings.CALLER_NAME,
                "target_name": target_name,
                "objective": objective,
                "spoken_brief": spoken_brief,
                "system_prompt": system_prompt,
            },
            "metadata": {
                "target_name": target_name,
                "category": category,
            },
        }

        resp = requests.post(
            f"{self.BASE_URL}/v2/create-phone-call",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )

        if resp.status_code not in (200, 201):
            err_msg = f"Retell AI Error ({resp.status_code}): {resp.text}"
            raise RuntimeError(err_msg)

        data = resp.json()
        call_id = data.get("call_id", f"retell_{int(time.time())}")

        call_tracker.register_call(
            call_id,
            {
                "target_name": target_name,
                "phone_number": e164_phone,
                "objective": objective,
                "provider": "retell",
            },
        )

        return {
            "call_id": call_id,
            "status": data.get("call_status", "queued"),
            "target_name": target_name,
            "phone_number": e164_phone,
            "provider": "retell",
            "raw": data,
        }

    def get_call(self, call_id: str) -> Dict[str, Any]:
        """Fetches call status and recording from Retell AI API."""
        resp = requests.get(f"{self.BASE_URL}/v2/get-call/{call_id}", headers=self._headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Failed to fetch Retell call {call_id}: {resp.text}")

    def end_call(self, call_id: str) -> Dict[str, Any]:
        """Terminates an ongoing Retell AI call."""
        resp = requests.post(f"{self.BASE_URL}/v2/end-call/{call_id}", headers=self._headers(), timeout=10)
        call_tracker.update_status(call_id, status="ended", ended_reason="user_hangup")
        if resp.status_code == 200:
            return {"call_id": call_id, "status": "ended"}
        return {"call_id": call_id, "status": "error", "response": resp.text}
