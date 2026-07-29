import socket
_orig_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda h, p, *a, **k: _orig_getaddrinfo(h, p, socket.AF_INET, *a[1:], **k)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.services.scheduler_service import scheduler_service

app = FastAPI(
    title="MeetFlow AI",
    description="Autonomous meeting intelligence and task routing platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    scheduler_service.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    scheduler_service.shutdown()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "meetflow-ai"}
