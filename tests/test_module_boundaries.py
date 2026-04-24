"""
P3-C: Module boundary CI guard.

Reads ``docs/domains.yaml`` and enforces that service modules only import
from their own domain, the shared kernel, or explicitly allowed cross-domain
dependencies.

The test walks every ``app/services/*.py`` file, parses its AST, extracts
``import`` / ``from ... import`` targets, maps each to a domain, and rejects
any import that violates the boundary rules.

Run:
    pytest tests/test_module_boundaries.py -v
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Dict, Optional, Set

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DOMAINS_YAML = ROOT / "docs" / "domains.yaml"

# ── Load domain manifest ────────────────────────────────────────────────

def _load_domains() -> dict:
    with open(DOMAINS_YAML, "r") as f:
        return yaml.safe_load(f)


def _build_module_to_domain_map(manifest: dict) -> Dict[str, str]:
    """Map dotted module paths → domain name.

    Shared kernel has priority: a module listed in ``shared`` keeps that
    assignment even if it also appears under a named domain.
    """
    m: Dict[str, str] = {}

    # Named domains first
    for domain_name, domain in manifest.get("domains", {}).items():
        for key in ("services", "models"):
            for mod in domain.get(key, []):
                m[mod] = domain_name

    # Shared kernel overwrites (higher priority)
    for key in ("models", "services", "core"):
        for mod in manifest.get("shared", {}).get(key, []):
            m[mod] = "shared"

    return m


def _get_allowed_domains(manifest: dict, domain_name: str) -> Set[str]:
    """Return the set of domain names a given domain may import from."""
    allowed = {"shared", domain_name}
    domain_cfg = manifest.get("domains", {}).get(domain_name, {})
    cross = domain_cfg.get("allowed_cross_domain", [])
    if "*" in cross:
        allowed.update(manifest.get("domains", {}).keys())
    else:
        allowed.update(cross)
    return allowed


# ── AST helpers ──────────────────────────────────────────────────────────

def _extract_imports(filepath: Path) -> list[str]:
    """Return all dotted import targets from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _module_path_from_file(filepath: Path) -> str:
    """Convert filesystem path to dotted module path.

    e.g. /project/app/services/wallet_service.py → app.services.wallet_service
    """
    rel = filepath.relative_to(ROOT)
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _resolve_import_to_known_module(
    imp: str, mod_to_domain: Dict[str, str]
) -> Optional[str]:
    """Try to match an import string to the longest known module prefix."""
    parts = imp.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in mod_to_domain:
            return candidate
    return None


# ── Test collection ──────────────────────────────────────────────────────

def _collect_service_files() -> list[Path]:
    services_dir = ROOT / "app" / "services"
    return sorted(services_dir.glob("*.py"))


def _collect_violations() -> list[tuple[str, str, str, str]]:
    """Return list of (source_module, import_target, source_domain, target_domain)."""
    manifest = _load_domains()
    mod_to_domain = _build_module_to_domain_map(manifest)
    violations: list[tuple[str, str, str, str]] = []

    for filepath in _collect_service_files():
        if filepath.name.startswith("__"):
            continue
        src_mod = _module_path_from_file(filepath)
        src_domain = mod_to_domain.get(src_mod)
        if src_domain is None:
            # Service not assigned to any domain — skip
            continue

        allowed = _get_allowed_domains(manifest, src_domain)
        for imp in _extract_imports(filepath):
            # Only police app.* imports
            if not imp.startswith("app."):
                continue
            known = _resolve_import_to_known_module(imp, mod_to_domain)
            if known is None:
                continue  # unmapped module — not policed yet
            target_domain = mod_to_domain[known]
            if target_domain not in allowed:
                violations.append((src_mod, known, src_domain, target_domain))

    return violations


# ── Tests ────────────────────────────────────────────────────────────────

class TestModuleBoundaries:
    """Enforce domain boundary rules from docs/domains.yaml."""

    def test_domains_yaml_exists(self):
        assert DOMAINS_YAML.exists(), "docs/domains.yaml not found"

    def test_domains_yaml_parseable(self):
        manifest = _load_domains()
        assert "shared" in manifest
        assert "domains" in manifest
        assert len(manifest["domains"]) >= 5

    def test_no_cross_domain_violations(self):
        """Every import in a service file must come from the same domain,
        the shared kernel, or an explicitly allowed cross-domain dependency."""
        violations = _collect_violations()
        if violations:
            lines = [
                f"  {src} → {tgt}  ({src_d} ✗ {tgt_d})"
                for src, tgt, src_d, tgt_d in violations
            ]
            pytest.fail(
                f"Cross-domain import violations ({len(violations)}):\n"
                + "\n".join(lines)
            )

    def test_every_service_file_assigned(self):
        """Warn (not fail) about service files not in any domain.

        This is advisory — new services should be slotted into a domain.
        """
        manifest = _load_domains()
        mod_to_domain = _build_module_to_domain_map(manifest)
        unassigned: list[str] = []
        for filepath in _collect_service_files():
            if filepath.name.startswith("__"):
                continue
            mod = _module_path_from_file(filepath)
            if mod not in mod_to_domain:
                unassigned.append(mod)
        # Advisory only — print but don't fail
        if unassigned:
            import warnings
            warnings.warn(
                f"{len(unassigned)} service(s) not assigned to a domain: "
                + ", ".join(unassigned[:10])
                + ("..." if len(unassigned) > 10 else ""),
                stacklevel=1,
            )

    def test_shared_kernel_is_not_empty(self):
        manifest = _load_domains()
        shared = manifest.get("shared", {})
        total = sum(len(shared.get(k, [])) for k in ("models", "services", "core"))
        assert total >= 5, "Shared kernel should list at least 5 modules"
