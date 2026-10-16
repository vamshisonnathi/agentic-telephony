"""
Configuration & Settings Management for Agentic Telephony.
Loads environment variables from .env with Pydantic type safety.
"""

from __future__ import annotations

import os
from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelephonySettings(BaseSettings):
    """Configuration settings for dual-engine AI telephony."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Active Provider: "vapi" or "retell"
    TELEPHONY_PROVIDER: Literal["vapi", "retell"] = "vapi"

    # Vapi AI Configuration
    VAPI_API_KEY: Optional[str] = None
    VAPI_PHONE_NUMBER_ID: Optional[str] = None
    VAPI_ASSISTANT_ID: Optional[str] = None
    VAPI_VOICE_ID: str = "Sagar"
    VAPI_VOICE_PROVIDER: str = "vapi"
    VAPI_LLM_MODEL: str = "gpt-4o"

    # Retell AI Configuration
    RETELL_API_KEY: Optional[str] = None
    RETELL_AGENT_ID: Optional[str] = None
    RETELL_FROM_NUMBER: Optional[str] = None

    # Caller & Persona Defaults
    CALLER_NAME: str = "Alex"
    CALLER_PHONE: Optional[str] = None
    DEFAULT_LOCATION: str = "nearby"

    # Webhook Server
    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8000
    WEBHOOK_URL: Optional[str] = None


# Global singleton settings
settings = TelephonySettings()
