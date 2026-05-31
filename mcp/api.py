"""HTTP exposer for web_search and web_extractor.

Thin FastAPI layer: validates requests, optional bearer auth, delegates to
`tools.py`. No provider-specific logic here.
"""

import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette.types import ASGIApp

from tools import web_extractor_impl, web_search_impl

API_TOKEN = os.environ.get("API_TOKEN", "").strip()
_bearer = HTTPBearer(auto_error=False)

_API_DESCRIPTION = (
    "REST API mirroring MCP tools web_search and web_extractor. "
    "Backends are selected from config/providers.yaml (fallback chain). "
    "Failures return HTTP 200 with an error field in the JSON body, same as MCP."
)


class SearchReq(BaseModel):
    query: str = Field(description="Search query string.")
    num_results: int = Field(
        default=10,
        description="Maximum results to return (clamped to 1–50).",
    )
    categories: str = Field(
        default="general",
        description=(
            'Topic filter (e.g. "general", "news", "science", "it", "images"). '
            "Mapped per active backend; some providers ignore unsupported values."
        ),
    )
    language: str = Field(
        default="auto",
        description='Language hint such as "en" or "vi", or "auto" for backend default.',
    )
    time_range: str | None = Field(
        default=None,
        description='Optional recency: "day", "week", "month", or "year".',
    )
    provider: str | None = Field(
        default=None,
        description=(
            'Force one search backend (no fallback): "tavily", "firecrawl", "exa", or "searxng". '
            "Omit to use the YAML chain."
        ),
    )


class ExtractReq(BaseModel):
    urls: str | list[str] = Field(
        description="One URL or a list of http/https URLs (max 20 per call).",
    )
    mode: str = Field(
        default="fit",
        description=(
            '"fit" (main content), "raw" (full page), or "bm25"/"llm" '
            "(relevance-filtered; requires query)."
        ),
    )
    query: str | None = Field(
        default=None,
        description='Focus query; required when mode is "bm25" or "llm".',
    )
    bypass_cache: bool = Field(
        default=False,
        description="Skip the server in-process cache and re-fetch from the active backend.",
    )
    provider: str | None = Field(
        default=None,
        description=(
            'Force one extract backend (no fallback): "tavily", "firecrawl", "exa", or "crawl4ai". '
            "Omit to use the YAML chain."
        ),
    )


def _require_api_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
) -> None:
    if not API_TOKEN:
        return
    if credentials is None or not secrets.compare_digest(
        credentials.credentials, API_TOKEN
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
        )


def create_app(mcp_app: ASGIApp | None = None) -> FastAPI:
    """Build the combined ASGI app: REST routes plus optional mounted MCP."""
    app = FastAPI(
        title="MCP Web Tools API",
        version="1.0.0",
        description=_API_DESCRIPTION,
        lifespan=getattr(mcp_app, "lifespan", None),
    )

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return {"ok": True}

    @app.post(
        "/api/v1/search",
        tags=["search"],
        dependencies=[Depends(_require_api_token)],
        summary="web_search",
        description=(
            "Search via the configured provider fallback chain. "
            "Same request/response contract as the web_search MCP tool."
        ),
    )
    async def search(req: SearchReq) -> dict:
        return await web_search_impl(**req.model_dump())

    @app.post(
        "/api/v1/extract",
        tags=["extract"],
        dependencies=[Depends(_require_api_token)],
        summary="web_extractor",
        description=(
            "Extract Markdown from URLs via the configured provider fallback chain. "
            "Same request/response contract as the web_extractor MCP tool."
        ),
    )
    async def extract(req: ExtractReq) -> dict:
        return await web_extractor_impl(**req.model_dump())

    if mcp_app is not None:
        app.mount("/mcp", mcp_app)

    return app
