import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Logging — configure once at entry point
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Lifespan — replaces deprecated @app.on_event
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Loomin-Docs backend starting up...")
    await init_db()
    logger.info("Startup complete.")
    yield
    # Shutdown
    logger.info("Loomin-Docs backend shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Loomin-Docs API",
    description="Air-gapped AI document editor backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes — imported here, registered as we build each one
# ---------------------------------------------------------------------------
from app.routes import health, documents, files, chat, tokens  # noqa: E402

app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(files.router, prefix="/files", tags=["Files"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(tokens.router, tags=["Tokens"])


@app.get("/", tags=["Root"])
async def root():
    return {"message": "Loomin-Docs API is running", "docs": "/docs"}