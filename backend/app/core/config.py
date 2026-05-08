# backend/app/core/config.py
# (Create this new file and paste this entire code)

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
# --- CRITICAL FIX: The Pydantic Bridge Import ---
from pydantic_settings import BaseSettings # standard compatibility bridge

# Standard standardized logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("chatbot-config")

# Ensure .env is loaded before settings class initialization
# NOTICE: Path is relative to backend root: ./
load_dotenv()


# --- Pydantic Bridge Settings Class (Fixes LangChain conflict) ---

# NOTICE: We are inheriting from BaseSettings provided by pydantic_settings, 
# not the original Pydantic BaseSettings from the monolithic script. 
# This class automatically reads variables from your environment.
class Settings(BaseSettings):
    """Secure, modular configuration service for MVP ship."""
    
    # --- Project Metadata ---
    # Standard: Default to production in the settings class
    APP_NAME: str = "AI Chatbot MVP"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "production").lower()
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    ALLOWED_ORIGINS_RAW: str = os.getenv("ALLOWED_ORIGINS", "")
    
    # --- Server Settings ---
    # Standard defaults: 0.0.0.0 is MANDATORY for standard cloud deployment
    HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("APP_PORT", 5000))
    # Standard: Multiple workers for standard concurrent requests (ASGI standard)
    WEB_CONCURRENCY: int = int(os.getenv("WEB_CONCURRENCY", 2))

    # --- Secure Secrets Handling (MANDATORY for Phase 1 ship) ---
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    # MUST be changed from default in real production via env
    JWT_SECRET_KEY: str | None = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"

    # Strict Validation: We enforce presence in production mode
    # We do not want the app starting and burning credits on fallbacks.
    def validate_production_secrets(self):
        if self.APP_ENV == "production" and not self.OPENAI_API_KEY:
            raise RuntimeError("FATAL: OPENAI_API_KEY environment variable MUST be set in production mode.")
        if self.APP_ENV == "production" and not self.JWT_SECRET_KEY:
            raise RuntimeError("FATAL: JWT_SECRET_KEY environment variable MUST be set in production mode.")

    # --- Multi-Tenancy (sites.json Driven) ---
    # NOTICE: We assume sites.json is in the project root: ../sites.json
    SITE_CONFIG_PATH: Path = Path(os.getenv("SITE_CONFIG_PATH", "../sites.json"))
    
    # Pre-calculated allowed origins parsed from env
    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        if self.ALLOWED_ORIGINS_RAW.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS_RAW.split(",") if origin.strip()]

    # --- AI / LLM / Vector Settings ---
    # NOTICE: Model versions are strictly env driven for easy upgrades.
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # [SCALABILITY FIX]: We standardize on Chroma-as-a-Service architecture.
    # Our app always tries to connect via HTTP, not local connections.
    CHROMA_SERVER_HOST: str | None = os.getenv("CHROMA_SERVER_HOST")
    CHROMA_SERVER_HTTP_PORT: str = os.getenv("CHROMA_SERVER_HTTP_PORT", "8000")

    # Segmented Local Vector Fallback pattern enforced
    # (If server host is missing, we use local segmented path: ./akinfoChroma/{site_id})
    # NOTICE: Path is relative to backend root: ./
    CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", "./akinfoChroma"))

    # Site-specific overrides repository
    # [SCALABILITY LIMITATION ACCEPTED]: Configurations are coupled to the file system.
    # We rely on mounting sites.json into the container for Phase 1 production.
    @property
    def SITE_CONFIGS(self) -> dict[str, dict[str, Any]]:
        """Single source of truth repository for allowed tenants."""
        
        # Internal default configuration structure
        default_site_config = {
            "brand_name": os.getenv("CHATBOT_BRAND", "AK Info Park"),
            "assistant_name": os.getenv("CHATBOT_ASSISTANT_NAME", "Assistant"),
            "welcome_message": os.getenv("CHATBOT_WELCOME_MESSAGE", "Hi, how can I assist you?"),
            "openai_chat_model": self.OPENAI_CHAT_MODEL,
            "system_prompt_suffix": os.getenv("SYSTEM_PROMPT_SUFFIX", ""),
            "theme": {
                "brand_color": "#2563eb",
                "brand_color_dark": "#1d4ed8",
                "surface_color": "#f8fafc",
                "bot_bubble_color": "#f1f5f9",
                "user_bubble_color": "#2563eb",
                "avatar_text": "AI",
            },
        }

        configs = {
            "default-site": {**default_site_config, "site_id": "default-site"}
        }

        # Tenant Configuration Validation - fine as is
        if not self.SITE_CONFIG_PATH.exists():
            logger.warning(f"Tenant config file not found at {self.SITE_CONFIG_PATH}. Using default only.")
            return configs

        try:
            raw_data = json.loads(self.SITE_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.exception("Failed to read multi-tenant site config file: %s", self.SITE_CONFIG_PATH)
            # This is a fatal startup error in multi-tenant SaaS.
            raise RuntimeError(f"Unable to read mandatory multi-tenant config file: {exc}") from exc

        # Standard Multi-tenant normalization and enforcement loop
        for site_id, raw_config in raw_data.items():
            if not isinstance(raw_config, dict):
                raise RuntimeError(f"Site config for '{site_id}' must be a JSON object.")
            
            # Merged with internal defaults for complete configuration
            raw_theme = raw_config.get("theme", {})
            if raw_theme and not isinstance(raw_theme, dict):
                raise RuntimeError(f"Theme config for '{site_id}' must be a JSON object.")

            merged = {**default_site_config, **raw_config, "site_id": site_id}
            merged["theme"] = {**default_site_config["theme"], **raw_theme}
            
            # Enforce segmented path patterns (e.g., allow overriding chroma_dir if needed)
            if settings.APP_ENV != "production" and not merged.get("chroma_dir"):
                # Notice we enforce the segmented local path `./akinfoChroma/{site_id}` that our cli tool uses
                merged["chroma_dir"] = str(self.CHROMA_DIR / site_id)

            configs[site_id] = merged

        return configs


# We instantiate settings once for singleton standard
settings = Settings()
# Execute critical secret validation
settings.validate_production_secrets()
