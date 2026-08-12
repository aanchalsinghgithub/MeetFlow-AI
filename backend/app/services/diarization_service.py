import os
import logging
from functools import lru_cache

import soundfile as sf
import torch

logger = logging.getLogger(__name__)

# NOTE: newer pyannote.audio releases resolve the old "speaker-diarization-3.1"
# slug to the pyannote/speaker-diarization-community-1 repo's assets (that's
# why the error in the logs mentions "community-1" even though the old code
# asked for "3.1"). We ask for it by its real name now so the error (if any)
# is less confusing.
DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"


@lru_cache(maxsize=1)
def _get_diarization_pipeline():
    """Load the pyannote pipeline once and reuse it for every chunk.

    BUGFIX: this used to be instantiated fresh inside diarize() on every
    call, reloading model weights from disk (or the HF Hub) for every ~15s
    audio chunk during a live meeting. Combined with the same issue in
    speech_service.py, this was the main reason real-time transcription
    fell progressively behind during a meeting.
    """
    from pyannote.audio import Pipeline

    hf_token = os.environ.get("HF_TOKEN")
    try:
        return Pipeline.from_pretrained(DIARIZATION_MODEL, token=hf_token)
    except TypeError:
        # Older pyannote.audio versions use the pre-rename argument name.
        return Pipeline.from_pretrained(DIARIZATION_MODEL, use_auth_token=hf_token)


class DiarizationService:
    # BUGFIX: lru_cache does NOT cache a raised exception, so every failed
    # pipeline load (e.g. the HF gated-repo 403 in the logs) was retried on
    # every single 15s chunk for the rest of the meeting — hammering the HF
    # Hub and spamming "DIARIZATION ERROR" once per chunk. Once we've seen
    # diarization fail in this process, stop retrying and just fall back to
    # "Unknown" speakers instead of eating the download/network cost again.
    _unavailable = False

    def diarize(self, audio_path: str) -> list[dict]:
        if DiarizationService._unavailable:
            return []

        from app.core.config import settings

        if not settings.enable_diarization:
            # NEW: lets diarization be turned off entirely without code
            # changes (ENABLE_DIARIZATION=false) — pyannote is a second
            # torch model loaded permanently alongside Whisper, and on a
            # RAM-constrained host the two together can be enough to OOM
            # on their own. Segments just come back "Unknown" instead of
            # "Speaker 1"/"Speaker 2"; the rest of the pipeline is
            # unaffected.
            return []

        try:
            pipeline = _get_diarization_pipeline()
            # BUGFIX: passing a raw file path makes pyannote try to decode
            # audio via torchcodec, which was failing silently on Windows
            # (missing/incompatible FFmpeg DLLs) and made every chunk fall
            # back to "Unknown" speakers. Loading the WAV ourselves with
            # soundfile and handing pyannote an in-memory waveform sidesteps
            # torchcodec entirely.
            waveform, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)
            tensor = torch.from_numpy(waveform.T)  # soundfile gives (time, channel); pyannote wants (channel, time)
            result = pipeline({"waveform": tensor, "sample_rate": sample_rate})

            # BUGFIX: community-1's output shape is NOT the same as the old
            # 3.1 pipeline's. 3.1 returned an Annotation directly, iterated
            # via `result.itertracks(yield_label=True)` -> (turn, track,
            # speaker) 3-tuples. community-1 returns a result object with a
            # `.speaker_diarization` attribute, iterated via
            # `for turn, speaker in result.speaker_diarization` -> 2-tuples
            # (per pyannote's own docs/examples). Using the old itertracks
            # call on a community-1 result raises AttributeError, which was
            # getting silently swallowed by the except below and marking
            # diarization "unavailable" even once HF access was fixed.
            # Handle both shapes so this works regardless of pyannote
            # version.
            speaker_diarization = getattr(result, "speaker_diarization", None)
            if speaker_diarization is not None:
                return [
                    {"speaker": speaker, "start": turn.start, "end": turn.end}
                    for turn, speaker in speaker_diarization
                ]
            return [
                {"speaker": speaker, "start": turn.start, "end": turn.end}
                for turn, _, speaker in result.itertracks(yield_label=True)
            ]
        except Exception as e:
            DiarizationService._unavailable = True
            logger.error(
                "Diarization disabled for the rest of this process (%s). "
                "If this is a 401/403 'gated repo' error, log into huggingface.co "
                "with the account that owns your HF_TOKEN, open "
                "https://huggingface.co/%s, click 'Agree and access repository', "
                "then restart the backend. All segments will be labelled "
                "'Unknown' until then.",
                e,
                DIARIZATION_MODEL,
            )
            return []
