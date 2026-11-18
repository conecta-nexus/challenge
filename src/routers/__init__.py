"""Routers package initialization."""

from src.routers.attachments import router as attachments_router
from src.routers.catalog import router as catalog_router
from src.routers.challenges import router as challenges_router

__all__ = [
    "attachments_router",
    "catalog_router",
    "challenges_router",
]
