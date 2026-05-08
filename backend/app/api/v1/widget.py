# backend/app/api/v1/widget.py
# (Create this new file and paste this entire code)

import logging
import time
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
import jwt

# Reusing configurations and core logic from our modular config service
from app.core.config import settings

# Setup standardized logging for this router
logger = logging.getLogger("chatbot-api-widget")

# APIRouter is the FastAPI standardized way to define modular routers
# that will later be registered to the main app.
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index():
    """Simple status check HTML page."""
    # MVP pattern: Notice we refer to setting.APP_ENV to output context.
    return HTMLResponse(
        f"<h1>Reusable multi-tenant chatbot backend is running ({settings.APP_ENV}).</h1>"
    )


@router.get("/healthz")
async def healthcheck():
    """Liveness check and multi-tenant status reporter."""
    # Phase 2: Add actual checks to database connections here.
    sites_summary = {}
    for site_id, site_config in settings.SITE_CONFIGS.items():
        sites_summary[site_id] = {
            "brand_name": site_config["brand_name"],
            # RAG Segmentation status reporter (Phase 2 readiness check)
            "chroma_config": "server" if settings.CHROMA_SERVER_HOST else "local fallback",
        }
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
        "site_count": len(settings.SITE_CONFIGS),
        "sites": sites_summary,
    }


@router.get("/widget-config")
async def widget_config(site_id: str = "default-site"):
    """Returns metadata for the front-end widget initialization."""
    # Standard multi-tenant validation pattern.
    try:
        site_config = settings.SITE_CONFIGS.get(site_id)
        if site_config is None:
            raise KeyError(site_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown site_id '{site_id}'.") from exc

    # NOTICE: We only return metadata. There is NO AI brain logic in this router.
    return {
        "siteId": site_id,
        "brandName": site_config["brand_name"],
        "assistantTitle": site_config["assistant_name"],
        "welcomeMessage": site_config["welcome_message"],
        "theme": site_config.get("theme", {}),
    }


@router.post("/token")
async def issue_widget_token(request: Request, site_id: str = "default-site"):
    """Issues a short-lived widget token for the requested tenant."""
    try:
        site_config = settings.SITE_CONFIGS.get(site_id)
        if site_config is None:
            raise KeyError(site_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown site_id '{site_id}'.") from exc

    if settings.APP_ENV == "production":
        origin = request.headers.get("origin")
        allowed_origins = site_config.get("allowed_origins", settings.ALLOWED_ORIGINS)
        if not origin or ("*" not in allowed_origins and origin not in allowed_origins):
            raise HTTPException(status_code=403, detail="Origin not allowed for this site.")

    now = int(time.time())
    payload = {
        "site_id": site_id,
        "iat": now,
        "exp": now + 60 * 60,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return {"token": token}
