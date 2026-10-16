"""
Phone Number E.164 Normalization & Validation Utility.
Converts arbitrary user-typed phone numbers into compliant E.164 standard (+1XXXXXXXXXX).
"""

from __future__ import annotations

import re
from typing import Optional


def to_e164_us(phone: str) -> Optional[str]:
    """
    Normalizes a US phone string into E.164 format (+1XXXXXXXXXX).
    Handles standard formats:
      - "(555) 123-4567" -> "+15551234567"
      - "555-123-4567"   -> "+15551234567"
      - "15551234567"    -> "+15551234567"
      - "+15551234567"   -> "+15551234567"
    """
    if not phone:
        return None

    clean = phone.strip()
    # Check if already fully compliant international E.164
    if re.match(r"^\+[1-9]\d{6,14}$", clean):
        return clean

    # Strip everything except digits
    digits = re.sub(r"\D", "", clean)

    # 10-digit standard US number
    if len(digits) == 10:
        return f"+1{digits}"

    # 11-digit US number starting with 1
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"

    # International without plus sign
    if len(digits) >= 11:
        return f"+{digits}"

    return None
