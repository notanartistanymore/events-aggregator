from enum import StrEnum


class EventStatus(StrEnum):
    PUBLISHED = "published"
    REGISTRATION_CLOSED = "registration_closed"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    NEW = "new"


class SyncStatus(StrEnum):
    NEVER = "never"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
