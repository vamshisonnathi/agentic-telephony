"""
Thread-safe Call State & Live Transcript Tracker.
Stores in-flight and historical phone call transcripts, turn-by-turn utterances,
recordings, and post-call AI summaries.
"""

from __future__ import annotations

import time
import threading
from typing import Dict, Any, List, Optional


class CallStateTracker:
    """Thread-safe store for active phone calls and live transcripts."""

    def __init__(self):
        self._calls: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register_call(self, call_id: str, metadata: Dict[str, Any]) -> None:
        """Initializes a new call record."""
        with self._lock:
            self._calls[call_id] = {
                "call_id": call_id,
                "provider": metadata.get("provider", "vapi"),
                "status": "queued",
                "target_name": metadata.get("target_name", "Unknown"),
                "phone_number": metadata.get("phone_number", ""),
                "objective": metadata.get("objective", ""),
                "started_at": time.time(),
                "updated_at": time.time(),
                "live_turns": [],
                "transcript": "",
                "summary": "",
                "ended_reason": "",
                "recording_url": "",
            }

    def update_transcript(self, call_id: str, role: str, text: str, is_partial: bool = False) -> None:
        """Appends or updates a live speaker utterance."""
        clean = text.strip()
        if not clean:
            return

        with self._lock:
            if call_id not in self._calls:
                return
            entry = self._calls[call_id]
            speaker = "AI" if role.lower() in ["bot", "assistant", "ai"] else "User"
            turns = entry["live_turns"]

            if turns and turns[-1]["speaker"] == speaker and turns[-1].get("partial"):
                turns[-1]["text"] = clean
                turns[-1]["partial"] = is_partial
            elif turns and turns[-1]["speaker"] == speaker and turns[-1]["text"] == clean:
                turns[-1]["partial"] = is_partial
            else:
                turns.append({"speaker": speaker, "text": clean, "partial": is_partial})

            entry["transcript"] = "\n".join([f"{t['speaker']}: {t['text']}" for t in turns])
            entry["updated_at"] = time.time()

    def update_status(
        self,
        call_id: str,
        status: str,
        summary: Optional[str] = None,
        ended_reason: Optional[str] = None,
        recording_url: Optional[str] = None,
    ) -> None:
        """Updates lifecycle status and end-of-call report data."""
        with self._lock:
            if call_id in self._calls:
                self._calls[call_id]["status"] = status
                if summary:
                    self._calls[call_id]["summary"] = summary
                if ended_reason:
                    self._calls[call_id]["ended_reason"] = ended_reason
                if recording_url:
                    self._calls[call_id]["recording_url"] = recording_url
                self._calls[call_id]["updated_at"] = time.time()

    def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single call snapshot."""
        with self._lock:
            return self._calls.get(call_id)

    def get_active_calls(self) -> List[Dict[str, Any]]:
        """Returns all currently connected, ringing, or queued calls."""
        with self._lock:
            return [
                c for c in self._calls.values()
                if c["status"] in ["queued", "ringing", "in-progress", "forwarding"]
            ]

    def list_all_calls(self) -> List[Dict[str, Any]]:
        """Returns all recorded calls ordered by started_at descending."""
        with self._lock:
            return sorted(list(self._calls.values()), key=lambda x: x["started_at"], reverse=True)


# Global singleton instance
call_tracker = CallStateTracker()
