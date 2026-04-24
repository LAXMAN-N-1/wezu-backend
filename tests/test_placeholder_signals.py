"""
P2-CI Guard: Scan money-flow, identity, and comms files for forbidden
placeholder / mock signals.

Any new placeholder leak will fail this test in CI.
"""
import re
import pathlib
import pytest

# ── Files under guard ────────────────────────────────────────────────────
# Grouped by P2 sub-phase for traceability.
GUARDED_FILES = {
    # P2-A: Money Flows
    "app/services/payment_service.py",
    "app/services/wallet_service.py",
    "app/services/settlement_service.py",
    "app/api/v1/payments.py",
    "app/api/v1/payments_enhanced.py",
    "app/api/v1/wallet.py",
    "app/api/v1/wallet_enhanced.py",
    "app/api/v1/settlements.py",
    # P2-B: Identity & KYC
    "app/services/kyc_service.py",
    "app/services/fraud_service.py",
    "app/api/v1/kyc.py",
    "app/api/v1/admin_kyc.py",
    "app/api/v1/fraud.py",
    # P2-C: Comms & Dealer
    "app/services/notification_service.py",
    "app/api/v1/notifications.py",
    "app/api/v1/notifications_enhanced.py",
    "app/api/v1/support.py",
    "app/api/v1/support_enhanced.py",
    "app/api/v1/dealer_analytics.py",
    "app/api/v1/dealer_campaigns.py",
    "app/api/v1/dealer_portal_dashboard.py",
}

# ── Forbidden signal patterns ────────────────────────────────────────────
# Each tuple: (compiled regex, human-readable label).
# We ignore case and look for patterns that indicate non-production code.
FORBIDDEN_PATTERNS = [
    (re.compile(r'\bplaceholder\b', re.IGNORECASE), "placeholder"),
    (re.compile(r'\bfake\b', re.IGNORECASE), "fake"),
    (re.compile(r'\bdummy\b', re.IGNORECASE), "dummy"),
    (re.compile(r'\bstub\b', re.IGNORECASE), "stub"),
    (re.compile(r'\bhardcoded\b', re.IGNORECASE), "hardcoded"),
    (re.compile(r'f"ENC_\{', re.IGNORECASE), 'mock encryption f"ENC_..."'),
]

# ── Known allowlist ──────────────────────────────────────────────────────
# Certain lines are acceptable (e.g. docstrings explaining what WAS removed,
# class names for MockKYCProvider that's guarded, etc.).
# Format: (relative file path, line number) — 1-indexed.
ALLOWLIST: set[tuple[str, int]] = {
    # MockKYCProvider class definition (guarded by RuntimeError in production)
    ("app/services/kyc_service.py", 15),
    ("app/services/kyc_service.py", 16),
}

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _scan_file(rel_path: str):
    """Scan a single file for forbidden signals. Returns list of violations."""
    full = ROOT / rel_path
    if not full.exists():
        return []  # file not present in workspace (e.g. not yet created)

    violations = []
    for lineno, line in enumerate(full.read_text().splitlines(), start=1):
        # Skip comments that are documenting the fix itself
        stripped = line.strip()
        if stripped.startswith("#") and any(
            kw in stripped.lower()
            for kw in ("p2", "removed", "replaced", "was", "prior", "legacy", "deconflicted")
        ):
            continue
        # Skip allowlisted lines
        if (rel_path, lineno) in ALLOWLIST:
            continue

        for pattern, label in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                violations.append(
                    f"  {rel_path}:{lineno}  [{label}]  {stripped[:120]}"
                )
    return violations


class TestPlaceholderSignals:
    """CI guard: no forbidden placeholder/mock signals in hardened files."""

    def test_no_placeholder_signals_in_money_flows(self):
        """P2-A: Money-flow files must have zero placeholder signals."""
        money_files = {f for f in GUARDED_FILES if "payment" in f or "wallet" in f or "settlement" in f}
        violations = []
        for f in sorted(money_files):
            violations.extend(_scan_file(f))
        assert not violations, (
            f"Placeholder signals detected in money-flow files:\n" + "\n".join(violations)
        )

    def test_no_placeholder_signals_in_identity(self):
        """P2-B: Identity & KYC files must have zero placeholder signals."""
        identity_files = {f for f in GUARDED_FILES if "kyc" in f or "fraud" in f}
        violations = []
        for f in sorted(identity_files):
            violations.extend(_scan_file(f))
        assert not violations, (
            f"Placeholder signals detected in identity files:\n" + "\n".join(violations)
        )

    def test_no_placeholder_signals_in_comms(self):
        """P2-C: Comms & dealer files must have zero placeholder signals."""
        comms_files = {
            f for f in GUARDED_FILES
            if "notification" in f or "support" in f or "dealer" in f
        }
        violations = []
        for f in sorted(comms_files):
            violations.extend(_scan_file(f))
        assert not violations, (
            f"Placeholder signals detected in comms/dealer files:\n" + "\n".join(violations)
        )
