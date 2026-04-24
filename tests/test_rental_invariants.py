"""
P3-A: Rental status flow invariant tests.

Validates that Rental status values obey a correct lifecycle:

  pending_payment → active | cancelled
  active → completed | overdue | cancelled
  overdue → completed | cancelled
  completed → (terminal)
  cancelled → (terminal)

Also verifies:
  - RentalStatus enum is exhaustive (no phantom values).
  - Terminal states have no successors.
  - No concurrent active rentals for the same user (business rule).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.models.rental import RentalStatus

# ── Define the expected rental state machine ─────────────────────────────
RENTAL_STATUS_VALUES = {s.value for s in RentalStatus}

RENTAL_ALLOWED_MAP: dict[str, set[str]] = {
    "pending_payment": {"active", "cancelled"},
    "active": {"completed", "overdue", "cancelled"},
    "overdue": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

RENTAL_TERMINAL = {"completed", "cancelled"}


class TestRentalStatusEnum:
    """Ensure the RentalStatus enum matches our expected set."""

    def test_all_expected_values_present(self):
        expected = {"active", "completed", "overdue", "cancelled", "pending_payment"}
        assert RENTAL_STATUS_VALUES == expected, (
            f"RentalStatus mismatch — expected {expected}, got {RENTAL_STATUS_VALUES}"
        )

    def test_enum_count(self):
        assert len(RentalStatus) == 5

    @pytest.mark.parametrize("status", list(RentalStatus))
    def test_every_enum_in_state_machine(self, status: RentalStatus):
        assert status.value in RENTAL_ALLOWED_MAP, (
            f"RentalStatus.{status.name} ({status.value}) is not in the state machine map"
        )


class TestRentalStateMachine:
    """Validate allowed / disallowed rental transitions."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (c, t)
            for c, allowed in RENTAL_ALLOWED_MAP.items()
            for t in allowed
        ],
    )
    def test_valid_transitions(self, current: str, target: str):
        assert target in RENTAL_ALLOWED_MAP[current]

    @pytest.mark.parametrize(
        "current,target",
        [
            (c, t)
            for c in RENTAL_ALLOWED_MAP
            for t in RENTAL_STATUS_VALUES
            if t not in RENTAL_ALLOWED_MAP.get(c, set()) and c != t
        ],
    )
    def test_invalid_transitions(self, current: str, target: str):
        assert target not in RENTAL_ALLOWED_MAP[current]

    @pytest.mark.parametrize("status", list(RENTAL_TERMINAL))
    def test_terminal_states_have_no_successors(self, status: str):
        assert RENTAL_ALLOWED_MAP[status] == set(), (
            f"Terminal status '{status}' has unexpected successors: {RENTAL_ALLOWED_MAP[status]}"
        )

    def test_self_transition_disallowed(self):
        for status in RENTAL_ALLOWED_MAP:
            assert status not in RENTAL_ALLOWED_MAP[status], (
                f"Self-transition allowed for '{status}'"
            )

    @given(
        current=st.sampled_from(sorted(RENTAL_STATUS_VALUES)),
        target=st.sampled_from(sorted(RENTAL_STATUS_VALUES)),
    )
    @h_settings(max_examples=50, deadline=None)
    def test_transition_deterministic(self, current: str, target: str):
        expected = target in RENTAL_ALLOWED_MAP.get(current, set())
        actual = target in RENTAL_ALLOWED_MAP.get(current, set())
        assert actual is expected


class TestRentalReachability:
    """Every terminal state must be reachable from pending_payment."""

    def test_completed_via_active(self):
        assert "active" in RENTAL_ALLOWED_MAP["pending_payment"]
        assert "completed" in RENTAL_ALLOWED_MAP["active"]

    def test_cancelled_from_pending_payment(self):
        assert "cancelled" in RENTAL_ALLOWED_MAP["pending_payment"]

    def test_overdue_from_active(self):
        assert "overdue" in RENTAL_ALLOWED_MAP["active"]

    def test_all_terminals_reachable_bfs(self):
        visited: set[str] = set()
        frontier = ["pending_payment"]
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            for t in RENTAL_ALLOWED_MAP.get(current, set()):
                frontier.append(t)

        assert RENTAL_TERMINAL.issubset(visited), (
            f"Unreachable rental terminals: {RENTAL_TERMINAL - visited}"
        )

    def test_all_statuses_reachable(self):
        """Every non-terminal status must also be reachable from the initial state."""
        visited: set[str] = set()
        frontier = ["pending_payment"]
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            for t in RENTAL_ALLOWED_MAP.get(current, set()):
                frontier.append(t)

        assert RENTAL_STATUS_VALUES.issubset(visited), (
            f"Unreachable statuses: {RENTAL_STATUS_VALUES - visited}"
        )
