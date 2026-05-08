# backend/app/api/v1/chat.py
# (Create this new file and paste this entire code)

import json
import logging
from typing import Any, Annotated

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from langchain_core.messages import HumanMessage, AIMessage

# Reusing core logic: Configurations, Security dependency, and the AI Brain.
from app.core.config import settings
from app.core.security import validate_websocket_token # MANDATORY GATEKEEPER
from app.services.ai import build_workflow # MANDATORY BRAIN

# Setup standardized logging for this critical router
logger = logging.getLogger("chatbot-api-chat")

router = APIRouter()

# --- Fallback Replies (Extracted UX helpers from monolithic script) ---

def build_runtime_unavailable_reply(user_input: str, site_config: dict[str, Any]) -> str:
    """Standard generic failure reply for Phase 1 ship."""
    # notice we return Markdown
    return "\n".join(
        [
            f"Thanks for your message about **{user_input}**.",
            "",
            f"The {site_config['brand_name']} assistant is temporarily unavailable right now.",
            "",
            "- The website widget is connected correctly.",
            "- The backend is running, but the AI service could not complete this request.",
            "- Please try again shortly, or contact the site team if the issue continues.",
            "",
            "What else can I help you test?",
        ]
    )

# --- SECURE WebSocket Handler (Extracted from monolithic script) ---

@router.websocket("/ws/{thread_id}")
async def websocket_chat(
    websocket: WebSocket, 
    thread_id: str, 
    # PHASE 1 SECURITY FIX: MANDATORY INJECTED AUTH DEPENDENCY.
    # The endpoint now *depends* on validate_websocket_token. If that returns None, 
    # this endpoint cannot be executed in production.
    token_payload: Annotated[dict[str, Any], Depends(validate_websocket_token)]
):
    """Secure, authenticated multi-tenant chat endpoint."""
    
    # [SCALABILITY FIX ACCEPTED]: To manage context, we are coupling history
    # to this specific app worker memory. For Phase 1, the client widget must handle
    # disconnections gracefully.
    
    origin = websocket.headers.get("origin")

    # PHASE 1 SECURITY FIX: Policy Violation Enforcement (Missing token in prod)
    if token_payload is None:
        await websocket.close(code=1008, reason="Client authentication (JWT) is required.")
        return

    # PHASE 1 SECURITY FIX: SPOOFING PROTECTION.
    # We use site_id derived from the SIGNED token, NOT from a user-supplied query param.
    site_id = token_payload.get("site_id", "default-site")

    # Standard Multi-tenant context validation
    try:
        site_config = settings.SITE_CONFIGS.get(site_id)
        if site_config is None:
            raise KeyError(site_id)
    except KeyError:
        await websocket.close(code=1008, reason=f"Token site_id '{site_id}' mismatch with configuration.")
        return

    # Standard MVP Origin validation against config
    allowed_origins = site_config.get("allowed_origins", settings.ALLOWED_ORIGINS)
    is_origin_allowed = ("*" in allowed_origins or origin in allowed_origins)
    if origin and settings.APP_ENV == "production" and not is_origin_allowed:
        logger.warning(f"Rejecting authenticated connection from unallowed origin: {origin} for site: {site_id}")
        await websocket.close(code=1008, reason="Origin not allowed for this site.")
        return

    # Connection accepted
    await websocket.accept()
    logger.info(f"WebSocket accepted: site_id={site_id}, thread_id={thread_id}, origin={origin}")
    
    # 1. Compile the AI Workflow brain for THIS specific site config.
    # Notice we refer to settings to find the segmented local vector store.
    workflow = build_workflow(site_config)
    
    # 2. Configurable 'MemorySaver' context coupling
    config = {"configurable": {"thread_id": f"{site_id}:{thread_id}"}}

    # 3. Send initial welcome message - fine as is
    await websocket.send_text(
        json.dumps(
            {
                "type": "welcome",
                "reply_markdown": site_config["welcome_message"],
                "site_id": site_id,
            }
        )
    )

    try:
        while True:
            # 4. Standard receive text loop
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_input = message_data.get("message", "").strip()

            if not user_input:
                continue

            # Standard AI Invocation pattern (Notice we use ainvoke for async standard)
            try:
                # 5. Invoke the AI brain with the new input
                # The AI Service (services/ai.py) handles its own timeouts/retriesinternally now
                # Result includes: 'input', 'chat_history', 'answer', 'context'.
                result = await workflow.ainvoke(
                    {"input": user_input, "chat_history": []},
                    config=config,
                )
                answer = result["answer"]
            except Exception:
                # 6. Generic failure reply UX helper
                # Notice we log this exception with critical context.
                logger.exception(
                    "RAG AI Brain Node critical failure after retries: thread_id=%s site_id=%s origin=%s",
                    thread_id,
                    site_id,
                    origin,
                )
                answer = build_runtime_unavailable_reply(user_input, site_config)

            # Standard Structured JSON Log Event (Removed file writing anti-pattern)
            logger.info(json.dumps({
                "event": "chat_reply",
                "thread_id": thread_id,
                "site_id": site_id,
                "origin": origin,
                "user_input": user_input,
                "ai_response": answer
            }))

            # 7. Standard send reply Markdown to client
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "reply",
                        "reply_markdown": answer,
                        "site_id": site_id,
                    }
                )
            )
    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected: thread_id=%s site_id=%s origin=%s",
            thread_id,
            site_id,
            origin,
        )
    except json.JSONDecodeError:
        logger.warning(f"Received invalid JSON from client on thread {thread_id}")
    except Exception:
        logger.exception(
            "WebSocket unexpected error: thread_id=%s site_id=%s origin=%s",
            thread_id,
            site_id,
            origin,
        )
        try:
            # Attempt to send one final error message before closing
            await websocket.close(code=1011, reason="Internal server error.")
        except:
            # Socket might already be closed
            pass