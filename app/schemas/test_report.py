from pydantic import BaseModel, RootModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# ------------------------------------------------
# Per-module result (used inside the POST body)
# ------------------------------------------------
class ModuleResult(BaseModel):
    """Represents the test results for a single module / test suite."""
    total_tests: int
    passed: int
    failed: int
    failures: Optional[List[Dict[str, Any]]] = None
    errors: Optional[List[Dict[str, Any]]] = None
    execution_time: Optional[str] = None
    environment: Optional[str] = "local"
    created_by: Optional[str] = "dev"


# Pydantic v2: use RootModel instead of __root__
class TestReportCreate(RootModel[Dict[str, ModuleResult]]):
    """
    Flexible payload supporting both pytest and schemathesis reports.

    Example:
    {
        "auth_tests": { "total_tests": 10, "passed": 9, "failed": 1, "failures": [...] },
        "payment_tests": { "total_tests": 5, "passed": 5, "failed": 0 }
    }
    """
    pass


# ------------------------------------------------
# Response schemas
# ------------------------------------------------
class TestReportRead(BaseModel):
    id: int
    module_name: str
    total_tests: int
    passed: int
    failed: int
    failures: Optional[Any] = None
    errors: Optional[Any] = None
    execution_time: str
    environment: str
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TestReportSaveResponse(BaseModel):
    status: str
    saved_count: int
    report_ids: List[int]
