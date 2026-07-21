import os
from functools import lru_cache
from pathlib import Path

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

    Also bumped "base" -> "small": "base" is the least accurate Whisper
    size and commonly mishears short proper nouns/names (e.g. "Rohit"
    heard as "it"). "small" is still fast enough on CPU and is
    meaningfully more accurate. Bump to "medium" instead if your CPU can
    handle the extra latency and you want even better accuracy.
    """
    from faster_whisper import WhisperModel

    return WhisperModel("small", device="cpu", compute_type="int8")


@lru_cache(maxsize=1)
def _get_openai_whisper_model():
    """Same caching fix for the openai-whisper fallback path."""
    import whisper

    return whisper.load_model("small")


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
