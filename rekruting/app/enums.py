from __future__ import annotations
from enum import StrEnum


class ReportStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProblemUrgency(StrEnum):
    URGENT = "urgent"
    MEDIUM = "medium"
    LOW = "low"


class MediaType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
