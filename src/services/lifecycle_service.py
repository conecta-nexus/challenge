"""Challenge lifecycle state transition rules and closure auditing."""

from uuid import UUID

from src.models.challenge import Challenge
from src.models.closure import ChallengeClosureLog


class ChallengeLifecycleError(ValueError):
    """Base exception for invalid challenge lifecycle operations."""


class InvalidChallengeTransitionError(ChallengeLifecycleError):
    """Raised when a requested status transition is not allowed."""

    def __init__(self, previous_status: str, target_status: str) -> None:
        self.previous_status = previous_status
        self.target_status = target_status
        super().__init__(
            f"Challenge status cannot transition from "
            f"'{previous_status}' to '{target_status}'"
        )


class ClosureReasonRequiredError(ChallengeLifecycleError):
    """Raised when a closure justification is missing or too short."""

    def __init__(self) -> None:
        super().__init__("Closure reason must contain at least 15 characters")


class LifecycleService:
    """Apply the allowed challenge state machine transitions."""

    MIN_CLOSURE_REASON_LENGTH = 15
    ALLOWED_TRANSITIONS = {
        "DRAFT": frozenset({"OPEN"}),
        "OPEN": frozenset({"CLOSED", "CANCELLED"}),
    }
    CLOSURE_STATUSES = frozenset({"CLOSED", "CANCELLED"})

    @classmethod
    def validate_transition(
        cls,
        previous_status: str,
        target_status: str,
        closure_reason: str | None = None,
    ) -> str | None:
        """Validate a transition and return a normalized closure reason."""
        current = cls._normalize_status(previous_status)
        target = cls._normalize_status(target_status)

        if target not in cls.ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise InvalidChallengeTransitionError(current, target)

        if target not in cls.CLOSURE_STATUSES:
            return None

        normalized_reason = (closure_reason or "").strip()
        if len(normalized_reason) < cls.MIN_CLOSURE_REASON_LENGTH:
            raise ClosureReasonRequiredError()

        return normalized_reason

    @classmethod
    def transition(
        cls,
        challenge: Challenge,
        target_status: str,
        changed_by: UUID,
        closure_reason: str | None = None,
    ) -> ChallengeClosureLog | None:
        """Update a challenge and create an audit log for voluntary closure."""
        previous_status = cls._normalize_status(challenge.status)
        normalized_target = cls._normalize_status(target_status)
        normalized_reason = cls.validate_transition(
            previous_status,
            normalized_target,
            closure_reason,
        )

        if normalized_target in cls.CLOSURE_STATUSES and challenge.id is None:
            raise ChallengeLifecycleError(
                "A persisted challenge ID is required to record a closure"
            )

        challenge.status = normalized_target

        if normalized_target not in cls.CLOSURE_STATUSES:
            return None

        return ChallengeClosureLog(
            challenge_id=challenge.id,
            closed_by=changed_by,
            previous_status=previous_status,
            target_status=normalized_target,
            closure_reason=normalized_reason,
        )

    @staticmethod
    def _normalize_status(status: str) -> str:
        """Return a non-empty uppercase status value."""
        if not isinstance(status, str) or not status.strip():
            raise ChallengeLifecycleError("Challenge status must be a non-empty string")
        return status.strip().upper()
