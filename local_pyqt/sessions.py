# sessions.py
# Persists chat sessions to a local JSON file for cross-run continuity.

from __future__ import annotations

import json
from pathlib import Path

SESSIONS_FILE = Path(__file__).parent / "chat_sessions.json"


def save_sessions(sessions: list[dict], last_idx: int = 0) -> None:
    """Serialise the in-memory sessions list to JSON."""
    try:
        data = {
            "last_session_idx": last_idx,
            "sessions": sessions,
        }
        SESSIONS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # never crash the app on a persistence failure


def load_sessions() -> tuple[list[dict], int]:
    """
    Read sessions from JSON.
    Returns (sessions, last_active_index).
    Returns ([], 0) if the file does not exist or is corrupt.
    """
    if not SESSIONS_FILE.exists():
        return [], 0
    try:
        raw = SESSIONS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        sessions: list[dict] = data.get("sessions", [])
        last_idx: int = int(data.get("last_session_idx", 0))
        # Validate: keep only sessions that have the required keys
        valid = [
            s for s in sessions
            if isinstance(s, dict)
            and isinstance(s.get("name"), str)
            and isinstance(s.get("history"), list)
        ]
        last_idx = max(0, min(last_idx, len(valid) - 1)) if valid else 0
        return valid, last_idx
    except Exception:
        return [], 0
