"""
Admin RBAC router re-export.

We reuse the comprehensive implementation under app.api.v1.admin_rbac
to avoid maintaining two divergent versions of the RBAC API. This keeps
the /api/v1/admin/rbac endpoints consistent with the test expectations.
"""

from app.api.v1.admin_rbac import router  # noqa: F401
