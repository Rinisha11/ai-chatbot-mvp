# backend/app/core/security.py
# (Create this new file and paste this entire code)

import logging
import time
from typing import Any, Annotated

import jwt  # <-- MANDATORY library standard
from fastapi import WebSocket, Query, Depends, HTTPException, status
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

# Reusing configurations from our modular config service
from ..core.config import settings

# Setup standardized logging for this service
logger = logging.getLogger("chatbot-security")

# --- Authentication Dependency (CRITICAL Phase 1 Fix) ---

def validate_websocket_token(
    websocket: WebSocket,
    # Standard MVP pattern: Pass token in query params as ws://...?token=JWT
    token: str | None = Query(default=None)
) -> dict[str, Any] | None:
    """Extracts and validates a signed JWT from a client backend."""
    
    # We always reject connections without tokens in production.
    if token is None:
        if settings.APP_ENV == "production":
            logger.warning("Rejecting connection attempt: Missing token query parameter.")
            # Standard WS close code for Policy Violation
            return None 
        else:
            # Allow during development without token - useful for local testing
            logger.info("Development mode: Allowing connection without token.")
            # Return a default, anonymized payload for development context
            return {"site_id": "default-site", "thread_id": "dev-thread"}

    try:
        # Standard Phase 1 implementation: We only validate the signature here.
        # This prevents basic spoofing from arbitrary backends.
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    
    # Standard error handling from the pyjwt library
    except ExpiredSignatureError:
        logger.warning("Rejecting connection attempt: Expired JWT token.")
        return None
    except InvalidTokenError:
        logger.warning("Rejecting connection attempt: Invalid JWT token signature.")
        return None
    except Exception:
        logger.exception("Unexpected error decoding JWT token.")
        return None