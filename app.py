"""
Render compatibility entrypoint.

Render's service is currently configured to run `gunicorn app:app`.
This module re-exports the FastAPI ASGI app from main.py so that command can
import successfully. The Render start command should still use an ASGI worker:

    gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
"""

from main import app

__all__ = ["app"]
