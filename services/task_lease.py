"""Ownership fencing shared by database writes and durable search workers."""
from contextvars import ContextVar


current_lease = ContextVar("hr_scorecard_lease", default=None)


class TaskLeaseLost(RuntimeError):
    """The worker must stop because another attempt owns this task."""


class PermanentTaskError(RuntimeError):
    """Retrying unchanged input would only repeat the same failure."""
