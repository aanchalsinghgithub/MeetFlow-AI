import logging
import os
from functools import lru_cache
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# BUGFIX: neither transcribe() call below passed a `language`, so Whisper
# ran its own language-ID model on every 15s chunk. Whisper's language
# detector only looks at the first ~30s of audio and is notoriously
# unreliable on short/quiet/noisy clips — a few seconds of silence, a
# cough, or background hum at the start of a chunk is enough for it to
# confidently guess Urdu, Korean, Welsh, etc. instead of English, even
# though every chunk in a single meeting is the same speaker(s)/language.
# Forcing the language removes that guesswork entirely.
#
# Override with the WHISPER_LANGUAGE env var (ISO-639-1 code, e.g. "hi",
# "es") if your meetings aren't in English. Set it to "" to restore
# auto-detection.
DEFAULT_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "en") or None

# BUGFIX: hardcoded "small" was still OOM-crashing the Render instance
# (see deploy events: repeated "Ran out of memory (used over 512MB)")
# even after diarization was disabled. "small" alone typically needs
# 400-500MB+ resident during inference; add FastAPI/SQLAlchemy/uvicorn's
# own baseline (~150-250MB) and a 512MB box has almost no headroom left,
# so a single chunk can tip it over. "base" cuts that to roughly
# 150-250MB with a real but smaller accuracy trade-off. Made this
# configurable (WHISPER_MODEL env var) instead of hardcoded so it can be
# bumped back to "small"/"medium" once the Render plan has more RAM,
# without another code change.
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")

# NEW: offload transcription to Groq's hosted Whisper API instead of
# loading any Whisper model into the Render process at all. This is the
# real fix for the OOM crash-loop - "base" still costs several hundred MB
# resident on a 512MB box, but Groq's endpoint runs on Groq's own
# hardware, so the backend process just makes an HTTP call and never
# loads a speech model into memory itself. Free tier (no card required,
# as of mid-2026): 2,000 requests/day, ~2 hours of audio per hour of
# clock time - comfortably covers normal meeting usage.
#
# Set GROQ_API_KEY to enable this path. If it's unset, or if a Groq call
# fails for any reason (rate limit, network blip, etc.), this falls back
# to the local faster-whisper/openai-whisper models below so a single
# Groq hiccup can't lose a chunk.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


@lru_cache(maxsize=1)
def _get_faster_whisper_model():
    """Load faster-whisper's model once and reuse it for every chunk.

    BUGFIX: this used to be instantiated fresh inside transcribe() on every
    call, which meant the model was reloaded from disk for every ~15s audio
    chunk during a live meeting. Loading a Whisper model takes several
    seconds even from a warm disk cache, so real-time transcription fell
    progressively further behind as a meeting went on. Caching it here loads
    it once (first chunk pays the cost) and reuses it for the rest of the
    meeting/process lifetime.

    Model size is controlled by WHISPER_MODEL (default "base" - see note
    above on the 512MB memory budget). Bump to "small" or "medium" via the
    env var if the instance has more RAM and you want better accuracy.
    """
    from faster_whisper import WhisperModel

    return WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


@lru_cache(maxsize=1)
def _get_openai_whisper_model():
    """Same caching fix for the openai-whisper fallback path."""
    import whisper

    return whisper.load_model(WHISPER_MODEL_SIZE)


class SpeechToTextService:
    def transcribe(
        self,
        audio_path: str,
        initial_prompt: str | None = None,
        language: str | None = None,
    ) -> list[dict]:
        # Explicit per-call `language` wins; otherwise fall back to the
        # configured default (English unless WHISPER_LANGUAGE says otherwise).
        lang = language or DEFAULT_LANGUAGE

        if GROQ_API_KEY:
            try:
                return self._transcribe_groq(audio_path, initial_prompt, lang)
            except Exception:
                logger.exception(
                    "Groq transcription failed for %s, falling back to local Whisper", audio_path
                )

        return self._transcribe_local(audio_path, initial_prompt, lang)

    @staticmethod
    def _transcribe_groq(audio_path: str, initial_prompt: str | None, lang: str | None) -> list[dict]:
        """Transcribe via Groq's hosted Whisper endpoint (OpenAI-compatible).

        Runs on Groq's hardware, not this process — nothing gets loaded
        into local memory. `response_format=verbose_json` returns segments
        with start times, matching the shape the local-model path returns.
        """
        with open(audio_path, "rb") as f:
            files = {"file": (Path(audio_path).name, f, "audio/wav")}
            data = {
                "model": GROQ_MODEL,
                "response_format": "verbose_json",
                "temperature": 0,
            }
            if lang:
                data["language"] = lang
            # Groq caps the prompt field at 224 tokens; our roster/title
            # prompt can run longer, so trim defensively rather than
            # letting the API reject the whole request over it.
            if initial_prompt:
                data["prompt"] = initial_prompt[:800]

            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            with httpx.Client(timeout=60) as client:
                response = client.post(GROQ_TRANSCRIPTION_URL, headers=headers, data=data, files=files)
            response.raise_for_status()

        result = response.json()
        return [
            {"speaker": "Unknown", "text": segment["text"], "timestamp": str(segment["start"])}
            for segment in result.get("segments", [])
        ]

    @staticmethod
    def _transcribe_local(audio_path: str, initial_prompt: str | None, lang: str | None) -> list[dict]:
        try:
            model = _get_faster_whisper_model()
            segments, _ = model.transcribe(
                audio_path,
                initial_prompt=initial_prompt,
                language=lang,
                task="transcribe",
                # Chunks are transcribed independently (one per HTTP request),
                # so there's no real "previous text" to condition on across
                # chunks — leaving this on made the model occasionally latch
                # onto a wrong-language guess from a noisy chunk and repeat it.
                condition_on_previous_text=False,
                vad_filter=True,
            )
            return [{"speaker": "Unknown", "text": segment.text, "timestamp": str(segment.start)} for segment in segments]
        except Exception:
            model = _get_openai_whisper_model()
            result = model.transcribe(
                str(Path(audio_path)),
                initial_prompt=initial_prompt,
                language=lang,
                task="transcribe",
                condition_on_previous_text=False,
            )
            return [{"speaker": "Unknown", "text": item["text"], "timestamp": str(item["start"])} for item in result["segments"]]
