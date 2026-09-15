"""Persisted history of generated speech clips."""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "bark-tts"
HISTORY_FILE = DATA_DIR / "history.json"


class HistoryStore:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._entries = self._load()

    def _load(self) -> list:
        if not HISTORY_FILE.exists():
            return []
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self):
        with open(HISTORY_FILE, "w") as f:
            json.dump(self._entries, f, indent=2)

    def new_audio_path(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return DATA_DIR / f"tts_{stamp}.wav"

    def add_entry(self, text: str, filepath: str, duration_sec: float) -> dict:
        entry = {
            "id": str(uuid.uuid4()),
            "text": text,
            "filepath": filepath,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duration_sec": duration_sec,
        }
        self._entries.insert(0, entry)
        self._save()
        return entry

    def list_entries(self) -> list:
        return list(self._entries)

    def remove_entry(self, entry_id: str):
        entry = next((e for e in self._entries if e["id"] == entry_id), None)
        if entry is None:
            return
        self._entries.remove(entry)
        self._save()
        try:
            os.remove(entry["filepath"])
        except OSError:
            pass
