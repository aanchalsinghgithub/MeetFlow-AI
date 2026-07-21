"""Speaker detection for meeting transcripts.

Wraps the existing :class:`app.services.diarization_service.DiarizationService`
(pyannote.audio) and assigns ``Speaker 1``, ``Speaker 2``, ... labels to
Whisper transcript segments based on which diarized speaker turn overlaps
each segment's time range.
"""
from __future__ import annotations

from pathlib import Path
import logging

from app.services.diarization_service import DiarizationService

logger = logging.getLogger(__name__)


class SpeakerService:
    def __init__(self) -> None:
        self.diarization = DiarizationService()

    def label_segments(self, audio_path: str | Path, segments: list[dict]) -> list[dict]:
        """Attach ``Speaker N`` labels to transcript segments.

        Falls back to the segment's existing speaker value (e.g. "Unknown")
        when diarization is unavailable or produces no turns.
        """
        turns = self.diarization.diarize(str(audio_path))
        if not turns:
            return segments

        speaker_order = self._speaker_order(turns)

        labeled = []
        for segment in segments:
            start = self._safe_float(segment.get("timestamp"))
            speaker_label = self._label_for(start, turns, speaker_order)
            labeled.append({**segment, "speaker": speaker_label or segment.get("speaker", "Unknown")})
        return labeled

    @staticmethod
    def _safe_float(value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _speaker_order(turns: list[dict]) -> dict[str, str]:
        """Map raw diarization speaker IDs to stable ``Speaker N`` labels in
        order of first appearance."""
        order: dict[str, str] = {}
        counter = 1
        for turn in sorted(turns, key=lambda t: t.get("start", 0)):
            raw_speaker = turn.get("speaker")
            if raw_speaker not in order:
                order[raw_speaker] = f"Speaker {counter}"
                counter += 1
        return order

    @staticmethod
    def _label_for(start: float | None, turns: list[dict], speaker_order: dict[str, str]) -> str | None:
        if start is None:
            return None
        for turn in turns:
            if turn.get("start", 0) <= start <= turn.get("end", 0):
                return speaker_order.get(turn.get("speaker"))
        return None
