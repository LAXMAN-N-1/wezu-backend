"""
Test Report Router
POST /api/v1/test-reports/         – save one or many module results
GET  /api/v1/test-reports/         – list all reports
GET  /api/v1/test-reports/{id}     – get a single report by id
GET  /api/v1/test-reports/module/{name} – filter by module name
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_db
from app.services.test_report_service import test_report_service
from app.schemas.test_report import TestReportRead, TestReportSaveResponse

router = APIRouter()


# ------------------------------------------------------------------
# POST /  – save test report (pytest OR schemathesis)
# ------------------------------------------------------------------
@router.post("/", response_model=TestReportSaveResponse, status_code=status.HTTP_201_CREATED)
def create_test_report(
    report: dict,
    db: Session = Depends(get_db),
):
    """
    Save a Pytest or Schemathesis test report.

    Body is a JSON object where each key is a module / suite name and the
    value contains the test results for that module.

    Example:
    ```json
    {
      "auth_tests": {
        "total_tests": 10,
        "passed": 9,
        "failed": 1,
        "failures": [{"name": "test_login", "message": "AssertionError"}],
        "errors": [],
        "environment": "local",
        "created_by": "dev"
      }
    }
    ```
    """
    try:
        saved = test_report_service.save_from_dict(db, report)
        return TestReportSaveResponse(
            status="success",
            saved_count=len(saved),
            report_ids=[r.id for r in saved],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# GET /  – list all test reports
# ------------------------------------------------------------------
@router.get("/", response_model=List[TestReportRead])
def list_test_reports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return a paginated list of all saved test reports."""
    return test_report_service.get_all(db, skip=skip, limit=limit)


# ------------------------------------------------------------------
# GET /module/{module_name}  – filter by module name
# ------------------------------------------------------------------
@router.get("/module/{module_name}", response_model=List[TestReportRead])
def get_reports_by_module(
    module_name: str,
    db: Session = Depends(get_db),
):
    """Return all reports for a specific module / test suite."""
    reports = test_report_service.get_by_module(db, module_name)
    if not reports:
        raise HTTPException(status_code=404, detail=f"No reports found for module '{module_name}'")
    return reports


# ------------------------------------------------------------------
# GET /{report_id}  – single report
# ------------------------------------------------------------------
@router.get("/{report_id}", response_model=TestReportRead)
def get_test_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Return a single test report by its ID."""
    report = test_report_service.get_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
