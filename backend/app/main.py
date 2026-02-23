import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.albums import router as albums_router
from app.api.auth import router as auth_router
from app.api.photos import router as photos_router
from app.api.search import router as search_router
from app.api.sync import router as sync_router
from app.core.config import settings
from app.jobs.workers import run_embedding_worker

app = FastAPI(title="Semantic Photo", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth_router)
app.include_router(photos_router)
app.include_router(search_router)
app.include_router(albums_router)
app.include_router(sync_router)


@app.on_event("startup")
async def start_worker() -> None:
    asyncio.create_task(run_embedding_worker())
    print("Worker started")


@app.get("/health")
async def health():
    return {"status": "ok"}
