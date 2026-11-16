from enum import StrEnum


class EventStatus(StrEnum):
    PUBLISHED = "published"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    NEW = "new"


class SyncStatus(StrEnum):
    NEVER = "never"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
