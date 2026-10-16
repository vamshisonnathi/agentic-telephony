"""
Base Telephony Provider Interface.
Defines standard contract for outbound dialing, call monitoring, and call termination.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTelephonyProvider(ABC):
    """Abstract interface that all telephony backends (Vapi, Retell, Twilio) implement."""

    @abstractmethod
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
        """Initiates an autonomous outbound phone call."""
        pass

    @abstractmethod
    def get_call(self, call_id: str) -> Dict[str, Any]:
        """Fetches live call status and artifacts from provider API."""
        pass

    @abstractmethod
    def end_call(self, call_id: str) -> Dict[str, Any]:
        """Terminates an in-progress phone call immediately."""
        pass
