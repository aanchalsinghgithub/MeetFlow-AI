"""Transcript generation for captured meeting audio.

Wraps the existing :class:`app.services.speech_service.SpeechToTextService`
(faster-whisper, with an openai-whisper fallback) and persists the result
incrementally to the ``transcripts`` table, formatted with ``[mm:ss]``
timestamps as requested by the transcript viewer.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import logging

from sqlalchemy.orm import Session

from app.models.entities import Meeting, Transcript
from app.services.speaker_service import SpeakerService
from app.services.speech_service import SpeechToTextService
from app.services.team_mapping import load_team_mapping

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self) -> None:
        self.speech = SpeechToTextService()
        self.speakers = SpeakerService()

    def transcribe_chunk(self, audio_path: str | Path, initial_prompt: str | None = None) -> list[dict]:
        """Transcribe a single audio chunk and attach speaker labels."""
        audio_path = str(audio_path)
        try:
            segments = self.speech.transcribe(audio_path, initial_prompt=initial_prompt)
        except Exception:
            logger.exception("Whisper transcription failed for %s", audio_path)
            return []

        try:
            return self.speakers.label_segments(audio_path, segments)
        except Exception:
            logger.exception("Speaker labelling failed for %s, returning unlabeled segments", audio_path)
            return segments

    def process_chunk_and_store(self, db: Session, meeting_id: int, audio_path: str | Path, chunk_offset_seconds: float = 0.0) -> list[Transcript]:
        """Transcribe a chunk and persist each turn as a Transcript row."""
        meeting = db.get(Meeting, meeting_id)

        # BUGFIX: this used to only hint Whisper with names pulled from
        # meeting.participants (calendar invite data), which is often
        # empty for ad-hoc meetings or when there's no calendar invite to
        # read attendees off of. Whisper's initial_prompt biases what it
        # *hears* -
        # a name it's been told to expect gets transcribed correctly far
        # more often than one it has to guess cold. Trying to fix wrong
        # words after the fact (a fixed list of "aacha" -> "Aanchal"
        # style aliases) can only ever cover mistakes you've already
        # seen; priming the model with your real team roster up front
        # covers mistakes you haven't seen yet too. So we now always
        # include the roster from team_mapping.json's "_people.members",
        # in addition to whatever calendar participants are known.
        roster = load_team_mapping().get("_people", {}).get("members", [])
        participant_names = [p.name for p in meeting.participants if p.name] if meeting else []
        prompt_parts = list(dict.fromkeys(  # de-dupe, keep order
            filter(None, [meeting.title if meeting else None, *participant_names, *roster])
        ))
        initial_prompt = ", ".join(prompt_parts) if prompt_parts else None

        segments = self.transcribe_chunk(audio_path, initial_prompt=initial_prompt)
        created: list[Transcript] = []

        for segment in segments:
            timestamp = self._format_timestamp(segment.get("timestamp"), chunk_offset_seconds)
            entry = Transcript(
                meeting_id=meeting_id,
                speaker=segment.get("speaker", "Unknown"),
                text=segment.get("text", "").strip(),
                timestamp=timestamp,
            )
            if not entry.text:
                continue
            db.add(entry)
            created.append(entry)

        if created:
            if meeting:
                meeting.transcript = meeting.transcript + [
                    {"speaker": e.speaker, "text": e.text, "timestamp": e.timestamp} for e in created
                ]
            db.commit()
            for entry in created:
                db.refresh(entry)

        return created

    @staticmethod
    def _format_timestamp(raw_seconds: str | float | None, chunk_offset_seconds: float) -> str:
        try:
            seconds = float(raw_seconds or 0) + chunk_offset_seconds
        except (TypeError, ValueError):
            seconds = chunk_offset_seconds
        delta = timedelta(seconds=max(seconds, 0))
        total_seconds = int(delta.total_seconds())
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
