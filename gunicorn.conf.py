"""Gunicorn configuration for Render.

Render is currently configured to run `gunicorn app:app`. Without this file,
Gunicorn uses its default synchronous WSGI worker, which cannot serve FastAPI's
ASGI application and causes:

    TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'

Gunicorn automatically loads `gunicorn.conf.py` from the working directory, so
this makes the existing Render command work without dashboard changes.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
