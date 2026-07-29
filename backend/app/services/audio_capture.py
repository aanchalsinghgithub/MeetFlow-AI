from __future__ import annotations

from pathlib import Path
import logging
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SECONDS = 15

# Windows audio device detected from ffmpeg
DEFAULT_AUDIO_DEVICE = "CABLE Output (VB-Audio Virtual Cable)"


class AudioCapture:
    """Captures audio in fixed-length WAV chunks using ffmpeg."""

    def __init__(
        self,
        meeting_id: int,
        output_dir: str | Path,
        input_device: str = DEFAULT_AUDIO_DEVICE,
        chunk_seconds: int = DEFAULT_CHUNK_SECONDS,
    ) -> None:
        self.meeting_id = meeting_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.input_device = input_device
        self.chunk_seconds = chunk_seconds

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._chunk_index = 0

    def start(self) -> None:
        """Start capturing audio in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name=f"audio-capture-{self.meeting_id}",
            daemon=True,
        )

        self._thread.start()

        logger.info(
            "Audio capture started for meeting %s using device '%s'",
            self.meeting_id,
            self.input_device,
        )

    def stop(self) -> None:
        """Stop audio capture."""
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=self.chunk_seconds + 5)

        logger.info(
            "Audio capture stopped for meeting %s",
            self.meeting_id,
        )

    def chunk_paths(self) -> list[Path]:
        return sorted(
            self.output_dir.glob("chunk_*.wav")
        )

    def _run(self) -> None:
        print(
            f"[AudioCapture] Started for meeting {self.meeting_id}"
        )

        while not self._stop_event.is_set():
            chunk_path = (
                self.output_dir
                / f"chunk_{self._chunk_index:05d}.wav"
            )

            try:
                self._capture_chunk(chunk_path)

            except FileNotFoundError:
                logger.error(
                    "ffmpeg not found for meeting %s",
                    self.meeting_id,
                )
                return

            except Exception as e:
                logger.exception(
                    "Audio capture failed: %s",
                    e,
                )

                time.sleep(1)
                continue

            self._chunk_index += 1

    def _capture_chunk(
        self,
        chunk_path: Path,
    ) -> None:
        """
        Capture one WAV chunk from Windows VB-CABLE.
        """

        print(
            f"[AudioCapture] Recording chunk -> {chunk_path}"
        )

        print(
            f"[AudioCapture] Device -> {self.input_device}"
        )

        command = [
            "ffmpeg",
            "-y",
            "-f",
            "dshow",
            "-i",
            f"audio={self.input_device}",
            "-t",
            str(self.chunk_seconds),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(chunk_path),
        ]

        process = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=self.chunk_seconds + 10,
        )

        if process.returncode != 0:
            raise RuntimeError(
                process.stderr.decode(
                    errors="ignore"
                )
            )

        print(
            f"[AudioCapture] Saved -> {chunk_path}"
        )