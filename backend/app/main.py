import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from app.api.albums import router as albums_router
from app.api.auth import router as auth_router
from app.api.memories import router as memories_router
from app.api.photos import router as photos_router
from app.api.search import router as search_router
from app.api.sync import router as sync_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.jobs.workers import run_daily_memories_job, run_embedding_worker
from app.services.drive_sync import sync_all_users

app = FastAPI(title="Semantic Photo", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
scheduler = AsyncIOScheduler()


def _allowed_origins() -> list[str]:
    origins = [settings.FRONTEND_URL.rstrip("/")]
    if settings.FRONTEND_URLS:
        extra = [item.strip().rstrip("/") for item in settings.FRONTEND_URLS.split(",") if item.strip()]
        origins.extend(extra)
    return list(dict.fromkeys(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(photos_router)
app.include_router(search_router)
app.include_router(albums_router)
app.include_router(sync_router)
app.include_router(memories_router)


@app.on_event("startup")
async def start_worker() -> None:
    asyncio.create_task(run_embedding_worker())
    scheduler.add_job(sync_all_users, "interval", minutes=30, id="drive_sync_all_users", replace_existing=True)
    scheduler.add_job(run_daily_memories_job, "cron", hour=8, minute=0, id="daily_memories_job", replace_existing=True)
    scheduler.start()
    print("Worker started")
    print("Drive sync scheduler started")
    print("Daily memories scheduler started")


@app.on_event("shutdown")
async def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
async def health():
    return {"status": "ok"}
