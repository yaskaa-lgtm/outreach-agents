"""SQLAlchemy ORM models. Every business table carries a `workspace_id` (multi-tenant ready).

Importing this package registers every table on `Base.metadata` (used by Alembic).
"""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.discovery import (
    Campaign,
    CampaignSegment,
    Company,
    Contact,
    Prospect,
    ProspectTransition,
)
from app.models.job import Job, ProviderCall
from app.models.llm_call import LLMCall
from app.models.offer import OfferProfile, Segment
from app.models.workspace import User, UserSession, Workspace

__all__ = [
    "AuditLog",
    "Base",
    "Campaign",
    "CampaignSegment",
    "Company",
    "Contact",
    "Job",
    "LLMCall",
    "OfferProfile",
    "Prospect",
    "ProspectTransition",
    "ProviderCall",
    "Segment",
    "User",
    "UserSession",
    "Workspace",
]
