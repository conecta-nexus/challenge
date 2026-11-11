"""Unit tests for challenge lifecycle transitions and closure auditing."""

from uuid import uuid4

import pytest

from src.models.challenge import Challenge
from src.models.closure import ChallengeClosureLog
from src.services.lifecycle_service import (
    ChallengeLifecycleError,
    ClosureReasonRequiredError,
    InvalidChallengeTransitionError,
    LifecycleService,
)


def build_challenge(status: str) -> Challenge:
    """Build a persisted-looking challenge for lifecycle unit tests."""
    return Challenge(
        id=uuid4(),
        company_id=uuid4(),
        title="Improve process traceability",
        description="A detailed challenge description",
        business_process="Operations",
        status=status,
        difficulty_level="INTERMEDIATE",
        modality="HYBRID",
        min_semester=6,
        economic_sector="Technology",
    )


def test_publish_transitions_draft_to_open_without_closure_log() -> None:
    """Allow publication without creating a closure audit record."""
    challenge = build_challenge("DRAFT")

    result = LifecycleService.transition(challenge, "OPEN", uuid4())

    assert result is None
    assert challenge.status == "OPEN"


@pytest.mark.parametrize("target_status", ["CLOSED", "CANCELLED"])
def test_closure_transitions_create_audit_log(target_status: str) -> None:
    """Allow justified closure states and capture their audit metadata."""
    challenge = build_challenge("OPEN")
    actor_id = uuid4()

    result = LifecycleService.transition(
        challenge,
        target_status.lower(),
        actor_id,
        "  Business priorities changed.  ",
    )

    assert isinstance(result, ChallengeClosureLog)
    assert challenge.status == target_status
    assert result.challenge_id == challenge.id
    assert result.closed_by == actor_id
    assert result.previous_status == "OPEN"
    assert result.target_status == target_status
    assert result.closure_reason == "Business priorities changed."


@pytest.mark.parametrize(
    ("previous_status", "target_status"),
    [
        ("DRAFT", "CLOSED"),
        ("DRAFT", "CANCELLED"),
        ("OPEN", "DRAFT"),
        ("OPEN", "OPEN"),
        ("IN_PROGRESS", "CLOSED"),
        ("CLOSED", "OPEN"),
        ("CANCELLED", "OPEN"),
    ],
)
def test_illegal_transitions_are_rejected(
    previous_status: str,
    target_status: str,
) -> None:
    """Reject transitions outside the explicit state machine."""
    challenge = build_challenge(previous_status)

    with pytest.raises(InvalidChallengeTransitionError) as exc_info:
        LifecycleService.transition(
            challenge,
            target_status,
            uuid4(),
            "A sufficiently detailed reason",
        )

    assert challenge.status == previous_status
    assert exc_info.value.previous_status == previous_status
    assert exc_info.value.target_status == target_status


@pytest.mark.parametrize(
    "closure_reason",
    [None, "", "   ", "Too short", "12345678901234"],
)
def test_closure_requires_fifteen_meaningful_characters(
    closure_reason: str | None,
) -> None:
    """Reject missing, blank, and shorter-than-15-character reasons."""
    challenge = build_challenge("OPEN")

    with pytest.raises(ClosureReasonRequiredError):
        LifecycleService.transition(
            challenge,
            "CLOSED",
            uuid4(),
            closure_reason,
        )

    assert challenge.status == "OPEN"


def test_closure_accepts_exact_fifteen_character_reason() -> None:
    """Accept the exact lower boundary after trimming whitespace."""
    challenge = build_challenge("OPEN")

    result = LifecycleService.transition(
        challenge,
        "CLOSED",
        uuid4(),
        "  123456789012345  ",
    )

    assert result is not None
    assert result.closure_reason == "123456789012345"


def test_closure_requires_persisted_challenge_id() -> None:
    """Prevent audit records that cannot reference a persisted challenge."""
    challenge = build_challenge("OPEN")
    challenge.id = None

    with pytest.raises(
        ChallengeLifecycleError,
        match="persisted challenge ID",
    ):
        LifecycleService.transition(
            challenge,
            "CLOSED",
            uuid4(),
            "A sufficiently detailed reason",
        )

    assert challenge.status == "OPEN"
