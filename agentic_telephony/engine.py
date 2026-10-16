"""
Unified Telephony Engine.
Coordinates provider selection (Vapi AI vs Retell AI), mission execution,
call state tracking, and call termination under a unified API.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
from agentic_telephony.config import settings
from agentic_telephony.providers.base import BaseTelephonyProvider
from agentic_telephony.providers.vapi import VapiProvider
from agentic_telephony.providers.retell import RetellProvider
from agentic_telephony.tracker import call_tracker, CallStateTracker


class TelephonyEngine:
    """
    Unified manager for autonomous voice calling and receiving.
    Seamlessly switches between Vapi AI and Retell AI providers.
    """

    def __init__(self, provider: Optional[str] = None):
        self._provider_name = (provider or settings.TELEPHONY_PROVIDER or "vapi").lower()
        self.vapi = VapiProvider()
        self.retell = RetellProvider()
        self.tracker: CallStateTracker = call_tracker

    @property
    def active_provider(self) -> BaseTelephonyProvider:
        """Returns the currently configured telephony provider instance."""
        if self._provider_name == "retell":
            return self.retell
        return self.vapi

    def set_provider(self, provider_name: str) -> None:
        """Dynamically switches active telephony provider ('vapi' or 'retell')."""
        clean = provider_name.lower().strip()
        if clean not in ("vapi", "retell"):
            raise ValueError(f"Unsupported provider '{provider_name}'. Must be 'vapi' or 'retell'.")
        self._provider_name = clean

    def place_call(
        self,
        phone_number: str,
        target_name: str,
        objective: str,
        spoken_brief: str,
        category: str = "general_inquiry",
        callee_identity: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        server_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches an autonomous phone call using the active or specified provider.
        """
        active = self.retell if (provider or self._provider_name) == "retell" else self.vapi
        return active.place_call(
            phone_number=phone_number,
            target_name=target_name,
            objective=objective,
            spoken_brief=spoken_brief,
            category=category,
            callee_identity=callee_identity,
            server_url=server_url,
        )

    def get_call_status(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves call status and transcripts from local tracker and provider API."""
        local = self.tracker.get_call(call_id)
        if not local:
            return None

        # Check provider API for updates if still in progress
        provider_name = local.get("provider", "vapi")
        client = self.retell if provider_name == "retell" else self.vapi

        try:
            remote = client.get_call(call_id)
            if provider_name == "vapi":
                remote_status = remote.get("status")
                summary = remote.get("summary") or remote.get("analysis", {}).get("summary")
                ended_reason = remote.get("endedReason")
                recording = remote.get("recordingUrl")
            else:
                remote_status = remote.get("call_status")
                summary = remote.get("call_analysis", {}).get("call_summary")
                ended_reason = remote.get("disconnection_reason")
                recording = remote.get("recording_url")

            if remote_status:
                self.tracker.update_status(
                    call_id,
                    status=remote_status,
                    summary=summary,
                    ended_reason=ended_reason,
                    recording_url=recording,
                )
        except Exception:
            pass

        return self.tracker.get_call(call_id)

    def end_call(self, call_id: str) -> Dict[str, Any]:
        """Terminates an in-progress call across local tracker and provider API."""
        local = self.tracker.get_call(call_id)
        provider_name = local.get("provider", "vapi") if local else self._provider_name
        client = self.retell if provider_name == "retell" else self.vapi
        return client.end_call(call_id)

    def get_active_calls(self) -> List[Dict[str, Any]]:
        """Returns all currently live calls."""
        return self.tracker.get_active_calls()


# Global singleton instance
telephony_engine = TelephonyEngine()
