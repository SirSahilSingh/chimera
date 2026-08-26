from __future__ import annotations

from backend.app.domain import DomainError


class InterventionError(DomainError):
    """Base error for operational lifecycle failures."""


class DecisionNotFoundError(InterventionError):
    pass


class InterventionNotFoundError(InterventionError):
    pass


class ActionMismatchError(InterventionError):
    pass


class InvalidLifecycleTransitionError(InterventionError):
    pass


class TerminalInterventionError(InterventionError):
    pass


class DuplicateInterventionError(InterventionError):
    pass


class ExecutorUnavailableError(InterventionError):
    pass


class InvalidExecutionContextError(InterventionError):
    pass


class InvalidOutcomeError(InterventionError):
    pass
