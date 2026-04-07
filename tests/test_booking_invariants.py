"""
P3-A: Booking state-machine invariant tests.

Validates that BatteryReservation status transitions obey the defined
state machine in BookingService.is_transition_allowed:

  PENDING  → {ACTIVE, CANCELLED, EXPIRED}
  ACTIVE   → {COMPLETED, CANCELLED}
  COMPLETED, CANCELLED, EXPIRED → (terminal, no further transitions)

Also verifies:
  - Terminal states cannot be exited.
  - Every valid transition is symmetric with is_transition_allowed.
  - Invalid transitions are rejected.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.booking_service import BookingService

ALL_STATUSES = ["PENDING", "ACTIVE", "COMPLETED", "CANCELLED", "EXPIRED"]
TERMINAL_STATUSES = {"COMPLETED", "CANCELLED", "EXPIRED"}
ALLOWED_MAP = {
    "PENDING": {"ACTIVE", "CANCELLED", "EXPIRED"},
    "ACTIVE": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
    "EXPIRED": set(),
}


class TestBookingStateTransitions:
    """Exhaustively verify the booking state machine."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (c, t)
            for c, allowed in ALLOWED_MAP.items()
            for t in allowed
        ],
    )
    def test_valid_transitions_accepted(self, current: str, target: str):
        assert BookingService.is_transition_allowed(current, target) is True

    @pytest.mark.parametrize(
        "current,target",
        [
            (c, t)
            for c in ALL_STATUSES
            for t in ALL_STATUSES
            if t not in ALLOWED_MAP.get(c, set()) and c != t
        ],
    )
    def test_invalid_transitions_rejected(self, current: str, target: str):
        assert BookingService.is_transition_allowed(current, target) is False

    @pytest.mark.parametrize("status", list(TERMINAL_STATUSES))
    def test_terminal_states_have_no_successors(self, status: str):
        for target in ALL_STATUSES:
            if target != status:
                assert BookingService.is_transition_allowed(status, target) is False

    def test_self_transition_disallowed(self):
        for status in ALL_STATUSES:
            assert BookingService.is_transition_allowed(status, status) is False

    @given(
        current=st.sampled_from(ALL_STATUSES),
        target=st.sampled_from(ALL_STATUSES),
    )
    @h_settings(max_examples=50, deadline=None)
    def test_transition_matches_map(self, current: str, target: str):
        expected = target in ALLOWED_MAP.get(current, set())
        assert BookingService.is_transition_allowed(current, target) is expected

    def test_case_insensitivity(self):
        """Transitions should be case-insensitive (internal normalization)."""
        assert BookingService.is_transition_allowed("pending", "ACTIVE") is True
        assert BookingService.is_transition_allowed("Pending", "active") is True
        assert BookingService.is_transition_allowed("ACTIVE", "completed") is True

    def test_whitespace_handling(self):
        """Leading/trailing whitespace must not break transitions."""
        assert BookingService.is_transition_allowed("  PENDING ", "ACTIVE") is True
        assert BookingService.is_transition_allowed("ACTIVE", " COMPLETED ") is True

    def test_unknown_status_rejects_all(self):
        """Unknown statuses must not match any transition."""
        for target in ALL_STATUSES:
            assert BookingService.is_transition_allowed("UNKNOWN", target) is False
        for current in ALL_STATUSES:
            assert BookingService.is_transition_allowed(current, "UNKNOWN") is False


class TestBookingStateReachability:
    """Verify every terminal state is reachable from PENDING."""

    def test_completed_reachable(self):
        """PENDING → ACTIVE → COMPLETED."""
        assert BookingService.is_transition_allowed("PENDING", "ACTIVE")
        assert BookingService.is_transition_allowed("ACTIVE", "COMPLETED")

    def test_cancelled_reachable_from_pending(self):
        """PENDING → CANCELLED."""
        assert BookingService.is_transition_allowed("PENDING", "CANCELLED")

    def test_cancelled_reachable_from_active(self):
        """PENDING → ACTIVE → CANCELLED."""
        assert BookingService.is_transition_allowed("PENDING", "ACTIVE")
        assert BookingService.is_transition_allowed("ACTIVE", "CANCELLED")

    def test_expired_reachable(self):
        """PENDING → EXPIRED."""
        assert BookingService.is_transition_allowed("PENDING", "EXPIRED")

    def test_all_terminals_reachable(self):
        """BFS from PENDING must reach all terminal states."""
        visited: set[str] = set()
        frontier = ["PENDING"]
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            for target in ALLOWED_MAP.get(current, set()):
                frontier.append(target)

        assert TERMINAL_STATUSES.issubset(visited), (
            f"Unreachable terminals: {TERMINAL_STATUSES - visited}"
        )
