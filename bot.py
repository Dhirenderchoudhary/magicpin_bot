"""Challenge entrypoint. `from bot import compose` and `uvicorn bot:app`."""

from src.bot import compose, respond
from src.main import app

__all__ = ["compose", "respond", "app"]
