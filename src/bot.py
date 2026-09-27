"""Submission entrypoint. `compose` is pure and does not need an API key."""

from .composer import compose, respond

__all__ = ["compose", "respond"]
