"""
Unit Tests for TelephonyEngine and CallStateTracker.
"""

import unittest
from unittest.mock import patch, MagicMock
from agentic_telephony.tracker import CallStateTracker
from agentic_telephony.engine import TelephonyEngine
from agentic_telephony.tools.resolver import to_e164_us


class TestEngineAndTracker(unittest.TestCase):
    def test_e164_normalization(self):
        self.assertEqual(to_e164_us("(555) 123-4567"), "+15551234567")
        self.assertEqual(to_e164_us("555-123-4567"), "+15551234567")
        self.assertEqual(to_e164_us("15551234567"), "+15551234567")
        self.assertEqual(to_e164_us("+15551234567"), "+15551234567")
        self.assertIsNone(to_e164_us("123"))

    def test_tracker_lifecycle(self):
        tracker = CallStateTracker()
        call_id = "test_call_101"
        tracker.register_call(call_id, {
            "target_name": "Test Pizza",
            "phone_number": "+15551234567",
            "objective": "Check gluten-free crust",
            "provider": "vapi",
        })

        call = tracker.get_call(call_id)
        self.assertIsNotNone(call)
        self.assertEqual(call["status"], "queued")
        self.assertEqual(call["target_name"], "Test Pizza")

        # Update live transcript
        tracker.update_transcript(call_id, "assistant", "Hi.", is_partial=False)
        tracker.update_transcript(call_id, "user", "Hello, do you want to order?", is_partial=False)

        call = tracker.get_call(call_id)
        self.assertEqual(len(call["live_turns"]), 2)
        self.assertIn("AI: Hi.", call["transcript"])
        self.assertIn("User: Hello, do you want to order?", call["transcript"])

        # Update end status
        tracker.update_status(call_id, status="ended", summary="Verified crust available.", ended_reason="completed")
        call = tracker.get_call(call_id)
        self.assertEqual(call["status"], "ended")
        self.assertEqual(call["summary"], "Verified crust available.")
        self.assertEqual(call["ended_reason"], "completed")

    def test_engine_provider_selection(self):
        engine = TelephonyEngine(provider="vapi")
        self.assertEqual(engine._provider_name, "vapi")

        engine.set_provider("retell")
        self.assertEqual(engine._provider_name, "retell")

        with self.assertRaises(ValueError):
            engine.set_provider("unsupported_backend")


if __name__ == "__main__":
    unittest.main()
