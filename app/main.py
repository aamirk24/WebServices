from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this later for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(auth_router)