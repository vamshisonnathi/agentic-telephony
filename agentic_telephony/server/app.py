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

    async def handle_list_active_calls(request: Request):
        active = telephony_engine.get_active_calls()
        return JSONResponse({"active_calls": active, "count": len(active)})

    async def handle_get_call_details(request: Request):
        call_id = request.path_params.get("call_id", "")
        info = telephony_engine.get_call_status(call_id)
        if not info:
            return JSONResponse({"error": "Call not found"}, status_code=404)
        return JSONResponse(info)

    async def handle_terminate_call(request: Request):
        call_id = request.path_params.get("call_id", "")
        res = telephony_engine.end_call(call_id)
        return JSONResponse(res)

    async def handle_websocket(websocket: WebSocket):
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
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app_instance.post("/webhook/vapi")(handle_vapi_webhook)
        app_instance.post("/webhook/retell")(handle_retell_webhook)
        app_instance.get("/api/calls/active")(handle_list_active_calls)
        app_instance.get("/api/calls/{call_id}")(handle_get_call_details)
        app_instance.post("/api/calls/{call_id}/end")(handle_terminate_call)
        app_instance.websocket("/ws/calls/{call_id}")(handle_websocket)
        return app_instance
    else:
        routes = [
            Route("/webhook/vapi", endpoint=handle_vapi_webhook, methods=["POST"]),
            Route("/webhook/retell", endpoint=handle_retell_webhook, methods=["POST"]),
            Route("/api/calls/active", endpoint=handle_list_active_calls, methods=["GET"]),
            Route("/api/calls/{call_id}", endpoint=handle_get_call_details, methods=["GET"]),
            Route("/api/calls/{call_id}/end", endpoint=handle_terminate_call, methods=["POST"]),
            WebSocketRoute("/ws/calls/{call_id}", endpoint=handle_websocket),
        ]
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
        return Starlette(routes=routes, middleware=middleware)


app = create_app()
