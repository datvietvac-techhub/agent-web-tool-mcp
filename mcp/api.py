"""HTTP exposer for web_search and web_extractor.

Thin FastAPI layer: validates requests, optional bearer auth, delegates to
`tools.py`. No SearXNG/Crawl4AI logic here.
"""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from starlette.types import ASGIApp

from tools import web_extractor_impl, web_search_impl

API_TOKEN = os.environ.get("API_TOKEN", "").strip()
_bearer = HTTPBearer(auto_error=False)


class SearchReq(BaseModel):
    query: str
    num_results: int = 10
    categories: str = "general"
    language: str = "auto"
    time_range: str | None = None
    provider: str | None = None


class ExtractReq(BaseModel):
    urls: str | list[str]
    mode: str = "fit"
    query: str | None = None
    bypass_cache: bool = False
    provider: str | None = None


def _require_api_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
) -> None:
    if not API_TOKEN:
        return
    if credentials is None or credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
        )


def create_app(mcp_app: ASGIApp | None = None) -> FastAPI:
    """Build the combined ASGI app: REST routes plus optional mounted MCP."""
    app = FastAPI(
        title="MCP Web Tools API",
        version="1.0.0",
        description="REST API for web_search and web_extractor",
        lifespan=getattr(mcp_app, "lifespan", None),
    )

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return {"ok": True}

    @app.post(
        "/api/v1/search",
        tags=["search"],
        dependencies=[Depends(_require_api_token)],
    )
    async def search(req: SearchReq) -> dict:
        return await web_search_impl(**req.model_dump())

    @app.post(
        "/api/v1/extract",
        tags=["extract"],
        dependencies=[Depends(_require_api_token)],
    )
    async def extract(req: ExtractReq) -> dict:
        return await web_extractor_impl(**req.model_dump())

    if mcp_app is not None:
        app.mount("/mcp", mcp_app)

    return app
