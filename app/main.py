from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.limiter import limiter
from app.scheduler import start_scheduler, stop_scheduler
from routers.annotations import router as annotations_router
from routers.auth import router as auth_router
from routers.authors import router as authors_router
from routers.crawl import router as crawl_router
from routers.papers import router as papers_router


def _infer_resource(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    return parts[0] if parts else "resource"


def _json_error(
    *,
    status_code: int,
    error: str,
    detail: str,
    **extra: object,
) -> JSONResponse:
    payload: dict[str, object] = {
        "error": error,
        "detail": detail,
    }
    payload.update(extra)
    return JSONResponse(status_code=status_code, content=payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)

app = FastAPI(
    title="ScholarGraph API",
    description="A research paper intelligence API for paper discovery, citation analysis, and semantic search.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this later for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        resource = _infer_resource(request.url.path)
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else f"{resource.capitalize()} was not found."
        )
        return _json_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error="not_found",
            detail=detail,
            resource=resource,
        )

    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else "Authentication required."
        )
        return _json_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="authentication_required",
            detail=detail,
        )

    if exc.status_code == status.HTTP_403_FORBIDDEN:
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else "You are authenticated but not authorised to access this resource."
        )
        return _json_error(
            status_code=status.HTTP_403_FORBIDDEN,
            error="forbidden",
            detail=detail,
        )

    if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else "Rate limit exceeded. Please try again later."
        )
        return _json_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error="rate_limit_exceeded",
            detail=detail,
        )

    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error."
    return _json_error(
        status_code=exc.status_code,
        error="http_error",
        detail=detail,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    field_errors: list[dict[str, str]] = []

    for err in exc.errors():
        loc_parts = [str(part) for part in err.get("loc", []) if part != "body"]
        field = ".".join(loc_parts) if loc_parts else "request"
        message = err.get("msg", "Invalid value.")
        field_errors.append(
            {
                "field": field,
                "message": message,
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "detail": "One or more fields failed validation.",
            "fields": field_errors,
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    return _json_error(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        error="rate_limit_exceeded",
        detail="Rate limit exceeded. Please try again later.",
    )


@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(crawl_router, prefix="/crawl", tags=["Crawling"])
app.include_router(papers_router, prefix="/papers", tags=["Papers"])
app.include_router(annotations_router, tags=["Annotations"])
app.include_router(authors_router, prefix="/authors", tags=["Authors"])