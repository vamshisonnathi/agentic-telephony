"""
Unit Tests for Telephony FastAPI Webhook Server.
"""

import unittest
from starlette.testclient import TestClient
from agentic_telephony.server.app import create_app
from agentic_telephony.tracker import call_tracker


class TestServerWebhooks(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_vapi_transcript_webhook(self):
        call_id = "vapi_webhook_test_1"
        call_tracker.register_call(call_id, {"target_name": "Test Bistro", "provider": "vapi"})

        payload = {
            "message": {
                "type": "transcript",
                "call": {"id": call_id},
                "role": "user",
                "transcript": "Yes we are open until 10 PM.",
                "transcriptType": "final",
            }
        }
        res = self.client.post("/webhook/vapi", json=payload)
        self.assertEqual(res.status_code, 200)

        call = call_tracker.get_call(call_id)
        self.assertIn("Yes we are open until 10 PM.", call["transcript"])

    def test_vapi_end_of_call_report(self):
        call_id = "vapi_webhook_test_2"
        call_tracker.register_call(call_id, {"target_name": "Test Bakery", "provider": "vapi"})

        payload = {
            "message": {
                "type": "end-of-call-report",
                "call": {"id": call_id},
                "summary": "Confirmed sourdough bread is available.",
                "endedReason": "customer-ended-call",
                "transcript": "AI: Hi. User: Yes we have bread.",
            }
        }
        res = self.client.post("/webhook/vapi", json=payload)
        self.assertEqual(res.status_code, 200)

        call = call_tracker.get_call(call_id)
        self.assertEqual(call["status"], "ended")
        self.assertEqual(call["summary"], "Confirmed sourdough bread is available.")
        self.assertEqual(call["ended_reason"], "customer-ended-call")

    def test_retell_webhook(self):
        call_id = "retell_webhook_test_1"
        call_tracker.register_call(call_id, {"target_name": "Dental Clinic", "provider": "retell"})

        payload = {
            "event": "call_ended",
            "call": {
                "call_id": call_id,
                "disconnection_reason": "agent_hangup",
                "transcript": "AI: Hi. User: We have an appointment at 2pm.",
            }
        }
        res = self.client.post("/webhook/retell", json=payload)
        self.assertEqual(res.status_code, 200)

        call = call_tracker.get_call(call_id)
        self.assertEqual(call["status"], "ended")
        self.assertEqual(call["ended_reason"], "agent_hangup")

    def test_list_active_calls_endpoint(self):
        res = self.client.get("/api/calls/active")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("active_calls", data)
        self.assertIn("count", data)


if __name__ == "__main__":
    unittest.main()
