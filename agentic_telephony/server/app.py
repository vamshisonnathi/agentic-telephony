"""
Inbound Call & Webhook Server for Real-Time Telephony.
Supports FastAPI (with OpenAPI docs) or Starlette fallback for lightweight zero-dependency setups.
Receives live webhooks from Vapi AI and Retell AI, streams live speech transcripts
over WebSockets, and provides REST endpoints for active call management.
"""

from __future__ import annotations

import json
from typing import Optional, Dict, Any, List

try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    _USE_FASTAPI = True
except ImportError:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.websockets import WebSocket, WebSocketDisconnect
    from starlette.exceptions import HTTPException
    from starlette.responses import JSONResponse
    from starlette.routing import Route, WebSocketRoute
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    _USE_FASTAPI = False

from agentic_telephony.config import settings
from agentic_telephony.engine import telephony_engine
from agentic_telephony.tracker import call_tracker


def verify_api_auth(request: Request) -> bool:
    """
    Verifies API shared-secret token for /api/* routes if API_SECRET_KEY is configured.
    Checks 'X-API-Key' header or 'Authorization: Bearer <key>'.
    If API_SECRET_KEY is None or empty, returns True (development / unconfigured mode).
    """
    required_key = settings.API_SECRET_KEY
    if not required_key:
        return True

    api_key_header = request.headers.get("x-api-key")
    if api_key_header and api_key_header == required_key:
        return True

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token == required_key:
            return True

    return False


def verify_webhook_auth(request: Request, provider: str = "vapi") -> bool:
    """
    Verifies webhook shared-secret / signature if WEBHOOK_SECRET is configured.
    Supports Vapi ('x-vapi-secret', 'authorization: Bearer <secret>')
    and Retell ('x-retell-secret', 'x-retell-signature', query param '?secret=').
    If WEBHOOK_SECRET is None or empty, returns True (development / unconfigured mode).
    """
    required_secret = settings.WEBHOOK_SECRET
    if not required_secret:
        return True

    if provider == "vapi":
        vapi_secret = request.headers.get("x-vapi-secret")
        if vapi_secret and vapi_secret == required_secret:
            return True
    elif provider == "retell":
        retell_secret = request.headers.get("x-retell-secret") or request.headers.get("x-retell-signature")
        if retell_secret and retell_secret == required_secret:
            return True

    generic_secret = request.headers.get("x-webhook-secret")
    if generic_secret and generic_secret == required_secret:
        return True

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:].strip() == required_secret:
        return True

    query_secret = request.query_params.get("secret")
    if query_secret and query_secret == required_secret:
        return True

    return False


def create_app() -> Any:
    """Creates and configures the FastAPI or Starlette telephony application."""

    # Active WebSocket clients listening to live transcripts
    active_websockets: Dict[str, List[WebSocket]] = {}

    async def broadcast_transcript(call_id: str, payload: Dict[str, Any]):
        clients = active_websockets.get(call_id, [])
        for ws in list(clients):
            try:
                await ws.send_json(payload)
            except Exception:
                if ws in clients:
                    clients.remove(ws)

    # --------------------------------------------------------------------------
    # Shared Webhook Handlers
    # --------------------------------------------------------------------------

    async def handle_vapi_webhook(request: Request):
        if not verify_webhook_auth(request, provider="vapi"):
            return JSONResponse({"error": "Unauthorized: Invalid or missing webhook secret"}, status_code=401)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

        msg = data.get("message", data)
        msg_type = msg.get("type", "")
        call = msg.get("call", {})
        call_id = call.get("id") or msg.get("callId") or data.get("callId")

        if not call_id:
            return JSONResponse({"status": "ignored", "reason": "no callId"}, status_code=200)

        if msg_type == "transcript":
            role = msg.get("role", "assistant")
            transcript_text = msg.get("transcript", "")
            is_partial = msg.get("transcriptType") == "partial"
            if transcript_text:
                call_tracker.update_transcript(call_id, role, transcript_text, is_partial=is_partial)
                await broadcast_transcript(call_id, {
                    "event": "transcript",
                    "speaker": role,
                    "text": transcript_text,
                    "partial": is_partial
                })

        elif msg_type == "conversation-update":
            messages = msg.get("messages", [])
            for m in messages:
                role = m.get("role", "assistant")
                txt = m.get("message") or m.get("content") or ""
                if txt:
                    call_tracker.update_transcript(call_id, role, txt, is_partial=False)

        elif msg_type == "status-update":
            status = msg.get("status", "in-progress")
            call_tracker.update_status(call_id, status=status)
            await broadcast_transcript(call_id, {"event": "status", "status": status})

        elif msg_type == "end-of-call-report":
            summary = msg.get("summary") or call.get("analysis", {}).get("summary") or ""
            ended_reason = msg.get("endedReason", "completed")
            recording = msg.get("recordingUrl") or call.get("artifact", {}).get("recordingUrl") or ""
            call_tracker.update_status(
                call_id,
                status="ended",
                summary=summary,
                ended_reason=ended_reason,
                recording_url=recording,
            )
            final_transcript = msg.get("transcript") or call.get("artifact", {}).get("transcript") or ""
            if final_transcript:
                call_tracker.update_transcript(call_id, "summary", final_transcript, is_partial=False)

            await broadcast_transcript(call_id, {
                "event": "ended",
                "summary": summary,
                "ended_reason": ended_reason,
                "recording_url": recording,
            })

        return JSONResponse({"status": "received", "type": msg_type, "call_id": call_id})

    async def handle_retell_webhook(request: Request):
        if not verify_webhook_auth(request, provider="retell"):
            return JSONResponse({"error": "Unauthorized: Invalid or missing webhook secret"}, status_code=401)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

        event = data.get("event")
        call = data.get("call", {})
        call_id = call.get("call_id")

        if not call_id:
            return JSONResponse({"status": "ignored", "reason": "no call_id"}, status_code=200)

        if event == "call_started":
            call_tracker.update_status(call_id, status="in-progress")
            await broadcast_transcript(call_id, {"event": "status", "status": "in-progress"})

        elif event == "call_ended":
            disconnection_reason = call.get("disconnection_reason", "completed")
            transcript = call.get("transcript", "")
            recording = call.get("recording_url", "")
            if transcript:
                call_tracker.update_transcript(call_id, "summary", transcript, is_partial=False)
            call_tracker.update_status(
                call_id,
                status="ended",
                ended_reason=disconnection_reason,
                recording_url=recording,
            )
            await broadcast_transcript(call_id, {"event": "ended", "reason": disconnection_reason})

        elif event == "call_analyzed":
            analysis = call.get("call_analysis", {})
            summary = analysis.get("call_summary", "")
            if summary:
                call_tracker.update_status(call_id, status="ended", summary=summary)
            await broadcast_transcript(call_id, {"event": "analyzed", "summary": summary})

        return JSONResponse({"status": "received", "event": event, "call_id": call_id})

    # --------------------------------------------------------------------------
    # REST API Handlers
    # --------------------------------------------------------------------------

    async def handle_dispatch_call(request: Request):
        if not verify_api_auth(request):
            return JSONResponse({"error": "Unauthorized: Invalid or missing API key"}, status_code=401)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        phone_number = body.get("phone_number")
        target_name = body.get("target_name")
        objective = body.get("objective")
        spoken_brief = body.get("spoken_brief")

        if not all([phone_number, target_name, objective, spoken_brief]):
            return JSONResponse(
                {"error": "Missing required fields: phone_number, target_name, objective, spoken_brief"},
                status_code=400,
            )

        category = body.get("category", "general_inquiry")
        provider = body.get("provider")

        try:
            call_res = telephony_engine.place_call(
                phone_number=phone_number,
                target_name=target_name,
                objective=objective,
                spoken_brief=spoken_brief,
                category=category,
                provider=provider,
            )
            return JSONResponse(call_res, status_code=201)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_list_active_calls(request: Request):
        if not verify_api_auth(request):
            return JSONResponse({"error": "Unauthorized: Invalid or missing API key"}, status_code=401)
        active = telephony_engine.get_active_calls()
        return JSONResponse({"active_calls": active, "count": len(active)})

    async def handle_get_call_details(request: Request):
        if not verify_api_auth(request):
            return JSONResponse({"error": "Unauthorized: Invalid or missing API key"}, status_code=401)
        call_id = request.path_params.get("call_id", "")
        info = telephony_engine.get_call_status(call_id)
        if not info:
            return JSONResponse({"error": "Call not found"}, status_code=404)
        return JSONResponse(info)

    async def handle_terminate_call(request: Request):
        if not verify_api_auth(request):
            return JSONResponse({"error": "Unauthorized: Invalid or missing API key"}, status_code=401)
        call_id = request.path_params.get("call_id", "")
        res = telephony_engine.end_call(call_id)
        return JSONResponse(res)

    async def handle_websocket(websocket: WebSocket):
        if settings.API_SECRET_KEY:
            token = websocket.query_params.get("token") or websocket.headers.get("x-api-key")
            if token != settings.API_SECRET_KEY:
                await websocket.close(code=4001)
                return

        await websocket.accept()
        call_id = websocket.path_params.get("call_id", "default")
        if call_id not in active_websockets:
            active_websockets[call_id] = []
        active_websockets[call_id].append(websocket)

        existing = call_tracker.get_call(call_id)
        if existing and existing.get("live_turns"):
            await websocket.send_json({"event": "initial_state", "call": existing})

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            if call_id in active_websockets and websocket in active_websockets[call_id]:
                active_websockets[call_id].remove(websocket)

    if _USE_FASTAPI:
        app_instance = FastAPI(
            title="Agentic Telephony Server",
            description="Autonomous AI Phone Calling & Receiving Webhook Server",
            version="1.0.0",
        )
        app_instance.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app_instance.post("/webhook/vapi")(handle_vapi_webhook)
        app_instance.post("/webhook/retell")(handle_retell_webhook)
        app_instance.post("/api/calls/dispatch")(handle_dispatch_call)
        app_instance.get("/api/calls/active")(handle_list_active_calls)
        app_instance.get("/api/calls/{call_id}")(handle_get_call_details)
        app_instance.post("/api/calls/{call_id}/end")(handle_terminate_call)
        app_instance.websocket("/ws/calls/{call_id}")(handle_websocket)
        return app_instance
    else:
        routes = [
            Route("/webhook/vapi", endpoint=handle_vapi_webhook, methods=["POST"]),
            Route("/webhook/retell", endpoint=handle_retell_webhook, methods=["POST"]),
            Route("/api/calls/dispatch", endpoint=handle_dispatch_call, methods=["POST"]),
            Route("/api/calls/active", endpoint=handle_list_active_calls, methods=["GET"]),
            Route("/api/calls/{call_id}", endpoint=handle_get_call_details, methods=["GET"]),
            Route("/api/calls/{call_id}/end", endpoint=handle_terminate_call, methods=["POST"]),
            WebSocketRoute("/ws/calls/{call_id}", endpoint=handle_websocket),
        ]
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=False,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
        return Starlette(routes=routes, middleware=middleware)


app = create_app()
