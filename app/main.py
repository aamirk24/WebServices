from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from routers.auth import router as auth_router
from app.limiter import limiter

from routers.crawl import router as crawl_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic goes here
    yield
    # Shutdown logic goes here


app = FastAPI(
    title="ScholarGraph API",
    description="A research paper intelligence API for paper discovery, citation analysis, and semantic search.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this later for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    return {"status": "ok"}

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(crawl_router, prefix="/crawl", tags=["Crawling"])