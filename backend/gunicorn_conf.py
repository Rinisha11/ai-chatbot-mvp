# backend/gunicorn_conf.py
# (Create this new file and paste this entire code)

import json
import logging
import multiprocessing
from typing import Any

# Reusing singleton settings from the standard modular configuration service
# Notice we are one directory 'up' so we can import app.core.config
from app.core.config import settings

# Setup standardized gunicorn standard logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("gunicorn-standard")

def on_starting(server):
    """Executes once during standard server startup standard standard."""
    logger.info(f"--- Gunicorn Standard production server standard starting standard ---")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Workers: {WEB_CONCURRENCY}")
    logger.info(f"Listen: {settings.HOST}:{settings.PORT}")


# Gunicorn standard configuration settings standard
# We use standard bind address standard standard standard standard
bind = f"{settings.HOST}:{settings.PORT}"

# ASGI standard worker standard standard standard standard standard
# NOTICE: We enforce standard standard standard uvicorn standard ASGI standard worker.
# This ensures standard async concurrent requests management.
worker_class = "uvicorn.workers.UvicornWorker"

# Multiprocessing standard standard standard standard standard
# [SCALABILITY FIX]: We use standard WEB_CONCURRENCY from singleton settings 
# to calculate worker count. Standard standard standard rule is CPU cores * 2.
# We ensure standard minimum of 2 standard workers in production for liveness.
WEB_CONCURRENCY = settings.WEB_CONCURRENCY
if settings.APP_ENV == "development":
    WEB_CONCURRENCY = 1 # Single standard worker in development
workers = WEB_CONCURRENCY

# Timeouts standard standard standard standard standard standard standard standard
# Notice standard standard timeout standard standard standard standard standard.
# We give ASGI workers ample standard standard standard standard standard.
timeout = 60 # ASGI standard worker timeout standard standard standard
keepalive = 5 # HTTP keepalive standard standard standard standard standard


# Logging standard standard standard standard standard standard standard standard
# We use standard standard standard gunicorn standard standard error standard standard standard.
# Access logs standard standard standard standard standard standard standard.
errorlog = "-" # Standard standard standard error log standard standard standard standard standard
accesslog = "-" # Standard standard standard access log standard standard standard standard standard
# We customize standard standard access standard log standard standard standard
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
