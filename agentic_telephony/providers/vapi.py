"""
Vapi AI Telephony Provider.
Communicates with Vapi REST API (https://api.vapi.ai) to dispatch outbound calls
and configure in-call voice synthesis, models, and real-time webhook callbacks.
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


class VapiProvider(BaseTelephonyProvider):
    """Client for Vapi AI outbound calling and live call management."""

    BASE_URL = "https://api.vapi.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        voice_id: Optional[str] = None,
        llm_model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.VAPI_API_KEY
        self.phone_number_id = phone_number_id or settings.VAPI_PHONE_NUMBER_ID
        self.assistant_id = assistant_id or settings.VAPI_ASSISTANT_ID
        self.voice_id = voice_id or settings.VAPI_VOICE_ID or "Sagar"
        self.voice_provider = settings.VAPI_VOICE_PROVIDER or "vapi"
        self.llm_model = llm_model or settings.VAPI_LLM_MODEL or "gpt-4o"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("VAPI_API_KEY is not configured. Set VAPI_API_KEY in .env or pass it to constructor.")
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
        """Dispatches an autonomous outbound phone call via Vapi."""
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

        webhook = server_url or settings.WEBHOOK_URL

        # Construct Vapi payload
        payload: Dict[str, Any] = {
            "customer": {"number": e164_phone},
        }

        if self.phone_number_id:
            payload["phoneNumberId"] = self.phone_number_id

        # Use pre-configured assistant or inline mission assistant
        if self.assistant_id:
            payload["assistantId"] = self.assistant_id
            payload["assistantOverrides"] = {
                "firstMessage": "Hi.",
                "model": {
                    "provider": "openai",
                    "model": self.llm_model,
                    "messages": [{"role": "system", "content": system_prompt}],
                },
                "variableValues": {
                    "target_name": target_name,
                    "objective": objective,
                    "caller_name": settings.CALLER_NAME,
                },
            }
            if webhook:
                payload["assistantOverrides"]["serverUrl"] = webhook
        else:
            # Full inline assistant definition
            inline_assistant: Dict[str, Any] = {
                "firstMessage": "Hi.",
                "model": {
                    "provider": "openai",
                    "model": self.llm_model,
                    "messages": [{"role": "system", "content": system_prompt}],
                },
                "voice": {
                    "provider": self.voice_provider,
                    "voiceId": self.voice_id,
                },
                "silenceTimeoutSeconds": 25,
                "maxDurationSeconds": 480,
                "backgroundSound": "off",
            }
            if webhook:
                inline_assistant["serverUrl"] = webhook
            payload["assistant"] = inline_assistant

        resp = requests.post(
            f"{self.BASE_URL}/call/phone",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )

        if resp.status_code not in (200, 201):
            err_msg = f"Vapi Error ({resp.status_code}): {resp.text}"
            raise RuntimeError(err_msg)

        data = resp.json()
        call_id = data.get("id", f"vapi_{int(time.time())}")

        call_tracker.register_call(
            call_id,
            {
                "target_name": target_name,
                "phone_number": e164_phone,
                "objective": objective,
                "provider": "vapi",
            },
        )

        return {
            "call_id": call_id,
            "status": data.get("status", "queued"),
            "target_name": target_name,
            "phone_number": e164_phone,
            "provider": "vapi",
            "raw": data,
        }

    def get_call(self, call_id: str) -> Dict[str, Any]:
        """Fetches live call data and transcripts from Vapi API."""
        resp = requests.get(f"{self.BASE_URL}/call/{call_id}", headers=self._headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        raise RuntimeError(f"Failed to fetch Vapi call {call_id}: {resp.text}")

    def end_call(self, call_id: str) -> Dict[str, Any]:
        """Terminates an ongoing Vapi call."""
        resp = requests.delete(f"{self.BASE_URL}/call/{call_id}", headers=self._headers(), timeout=10)
        call_tracker.update_status(call_id, status="ended", ended_reason="user_hangup")
        if resp.status_code in (200, 204):
            return {"call_id": call_id, "status": "ended"}
        return {"call_id": call_id, "status": "error", "response": resp.text}
