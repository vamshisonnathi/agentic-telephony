"""
Unit Tests for Telephony FastAPI Webhook Server & Authentication.
"""

import unittest
from starlette.testclient import TestClient
from agentic_telephony.config import settings
from agentic_telephony.server.app import create_app
from agentic_telephony.tracker import call_tracker


class TestServerWebhooks(unittest.TestCase):
    def setUp(self):
        self._orig_api_secret = settings.API_SECRET_KEY
        self._orig_webhook_secret = settings.WEBHOOK_SECRET
        settings.API_SECRET_KEY = None
        settings.WEBHOOK_SECRET = None
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        settings.API_SECRET_KEY = self._orig_api_secret
        settings.WEBHOOK_SECRET = self._orig_webhook_secret

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

    def test_api_auth_protection(self):
        settings.API_SECRET_KEY = "super_secret_token_xyz"
        try:
            # 1. Unauthenticated request should be rejected with 401
            unauth_res = self.client.get("/api/calls/active")
            self.assertEqual(unauth_res.status_code, 401)

            # 2. Invalid API key should be rejected with 401
            bad_key_res = self.client.get("/api/calls/active", headers={"x-api-key": "wrong_key"})
            self.assertEqual(bad_key_res.status_code, 401)

            # 3. Valid X-API-Key header should succeed with 200
            valid_x_key_res = self.client.get("/api/calls/active", headers={"x-api-key": "super_secret_token_xyz"})
            self.assertEqual(valid_x_key_res.status_code, 200)

            # 4. Valid Authorization Bearer header should succeed with 200
            valid_bearer_res = self.client.get("/api/calls/active", headers={"Authorization": "Bearer super_secret_token_xyz"})
            self.assertEqual(valid_bearer_res.status_code, 200)
        finally:
            settings.API_SECRET_KEY = None

    def test_webhook_auth_protection(self):
        settings.WEBHOOK_SECRET = "wh_secret_abc123"
        try:
            payload = {"message": {"type": "transcript", "call": {"id": "auth_test_1"}}}

            # 1. Unauthenticated webhook rejected with 401
            unauth = self.client.post("/webhook/vapi", json=payload)
            self.assertEqual(unauth.status_code, 401)

            # 2. Invalid secret rejected with 401
            bad_sec = self.client.post("/webhook/vapi", json=payload, headers={"x-vapi-secret": "wrong"})
            self.assertEqual(bad_sec.status_code, 401)

            # 3. Valid Vapi secret header succeeds
            valid = self.client.post("/webhook/vapi", json=payload, headers={"x-vapi-secret": "wh_secret_abc123"})
            self.assertEqual(valid.status_code, 200)

            # 4. Valid Retell secret header succeeds
            retell_payload = {"event": "call_started", "call": {"call_id": "auth_test_2"}}
            valid_retell = self.client.post("/webhook/retell", json=retell_payload, headers={"x-retell-secret": "wh_secret_abc123"})
            self.assertEqual(valid_retell.status_code, 200)
        finally:
            settings.WEBHOOK_SECRET = None


if __name__ == "__main__":
    unittest.main()
