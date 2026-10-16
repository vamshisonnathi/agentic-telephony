"""
Unit Tests for the 4-Pillar Human Transaction Protocol (AHTP) & Identity Extraction.
"""

import unittest
from agentic_telephony.protocol import (
    extract_callee_identity,
    build_mission_call_prompt,
    HUMAN_CONVERSATION_RULES,
)


class TestProtocolAndIdentity(unittest.TestCase):
    def test_extract_callee_identity_paren_male(self):
        res = extract_callee_identity("Call David (my brother) to see if he arrived")
        self.assertEqual(res["name"], "David")
        self.assertEqual(res["relation"], "brother")
        self.assertEqual(res["pronouns"], "he/him")
        self.assertIn("ALWAYS use he/him", res["rule"])

    def test_extract_callee_identity_paren_female(self):
        res = extract_callee_identity("Please phone Sarah (my sister) and tell her dinner is ready")
        self.assertEqual(res["name"], "Sarah")
        self.assertEqual(res["relation"], "sister")
        self.assertEqual(res["pronouns"], "she/her")
        self.assertIn("ALWAYS use she/her", res["rule"])

    def test_extract_callee_identity_direct_name(self):
        res = extract_callee_identity("Call Marcus about tomorrow's schedule")
        self.assertEqual(res["name"], "Marcus")
        self.assertIn("they/them", res["pronouns"])

    def test_mission_prompt_contains_4_pillars(self):
        prompt = build_mission_call_prompt(
            target_name="Acme Supplies",
            objective="Check if they have 50 folding chairs",
            spoken_brief="1. Ask for availability. 2. Get price. 3. Ask for confirmation text.",
            category="general_inquiry",
            caller_name="Alex",
            caller_phone="+15551234567",
        )
        self.assertIn("UNIVERSAL 4-PILLAR HUMAN TRANSACTION PROTOCOL", prompt)
        self.assertIn("PILLAR 1: CASUAL OPENING & CONVERSATIONAL RECOVERY", prompt)
        self.assertIn("PILLAR 2: STRICT PRONOUN RULE & BREVITY", prompt)
        self.assertIn("PILLAR 3: REAL-WORLD MICRO-MATH & LOGISTICS VALIDATION", prompt)
        self.assertIn("PILLAR 4: 360° TRANSACTION CLOSURE", prompt)
        self.assertIn("Alex", prompt)
        self.assertIn("+15551234567", prompt)

    def test_direct_contact_prompt(self):
        prompt = build_mission_call_prompt(
            target_name="Mom",
            objective="Confirm if she received the package",
            spoken_brief="Say hi and ask if package arrived safely.",
            category="direct_call",
            callee_identity={"name": "Mom", "pronouns": "she/her", "rule": "Use she/her"},
            caller_name="Jordan",
        )
        self.assertIn("casual phone call with a contact", prompt)
        self.assertIn("Jordan", prompt)
        self.assertIn("she/her", prompt)


if __name__ == "__main__":
    unittest.main()
