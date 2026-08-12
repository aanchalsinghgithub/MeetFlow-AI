from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./meetflow.db"
    redis_url: str = "redis://localhost:6379/0"
    mistral_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None

    # NEW: Render's free web services block outbound traffic on every SMTP
    # port (25, 465, 587) as of Sep 2025 - so smtp_host/smtp_username/
    # smtp_password above can be perfectly correct and email will still
    # never send on a free instance; it's a network-level block, not a
    # credentials problem. Brevo's email API goes over plain HTTPS (443),
    # which isn't blocked, so email_service.py now sends through it when
    # configured. Get a free key (300 emails/day, no card) at
    # https://app.brevo.com/settings/keys/api. brevo_sender_email must be
    # a sender you've verified in Brevo (Settings -> Senders).
    brevo_api_key: str | None = None
    brevo_sender_email: str | None = None
    brevo_sender_name: str = "MeetFlow AI"

    backend_cors_origins: str = (
    "http://localhost:5173,"
    "https://meetflow-ai-frontend.vercel.app"
     )

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/calendar/callback"
    frontend_url: str = "http://localhost:5173"

    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    slack_webhook_url: str | None = None

    # BUGFIX: speaker diarization (pyannote) is a second, separately-loaded
    # torch model kept in memory alongside Whisper for the whole process
    # lifetime — on a RAM-constrained host (e.g. Render's free 512MB tier)
    # loading both at once can be enough on its own to OOM, with nothing
    # to do with any other feature. This was the main remaining cause of
    # the backend crash-looping (502/503) during live capture. The
    # product doesn't need "who said what" (see diarization_service.py /
    # speaker_service.py), so this now defaults to false: pyannote is
    # never imported or loaded, and every segment is just labelled
    # "Unknown" instead of "Speaker 1"/"Speaker 2". Can still be turned
    # back on with ENABLE_DIARIZATION=true if that ever changes.
    enable_diarization: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
