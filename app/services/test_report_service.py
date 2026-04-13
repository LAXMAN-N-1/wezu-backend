"""
Test Report Service
Handles saving pytest / schemathesis test results to the database.
"""
import time
import json
from typing import List
from sqlmodel import Session, select
from app.models.test_report import TestReport


class TestReportService:

    # ------------------------------------------------------------------
    # SAVE – accepts the dict payload {module_name: {results...}}
    # ------------------------------------------------------------------
    @staticmethod
    def save_from_dict(db: Session, report_dict: dict) -> List[TestReport]:
        """
        Persist one TestReport row per module_name found in report_dict.

        Expected shape:
            {
                "auth_tests": {
                    "total_tests": 10, "passed": 9, "failed": 1,
                    "failures": [...], "errors": [...],
                    "environment": "local", "created_by": "ci"
                },
                ...
            }
        """
        saved: List[TestReport] = []
        start = time.time()

        for module_name, results in report_dict.items():
            # Support both dict-like objects (Pydantic models) and plain dicts
            if hasattr(results, "dict"):
                results = results.dict()

            exec_time = results.get("execution_time") or f"{round(time.time() - start, 2)}s"

            report = TestReport(
                module_name=module_name,
                total_tests=results.get("total_tests", 0),
                passed=results.get("passed", 0),
                failed=results.get("failed", 0),
                failures=results.get("failures"),
                errors=results.get("errors"),
                execution_time=exec_time,
                environment=results.get("environment", "local"),
                created_by=results.get("created_by", "dev"),
            )
            db.add(report)
            saved.append(report)

        db.commit()
        for r in saved:
            db.refresh(r)

        return saved

    # ------------------------------------------------------------------
    # GET ALL
    # ------------------------------------------------------------------
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[TestReport]:
        return db.exec(select(TestReport).offset(skip).limit(limit)).all()

    # ------------------------------------------------------------------
    # GET BY ID
    # ------------------------------------------------------------------
    @staticmethod
    def get_by_id(db: Session, report_id: int) -> TestReport | None:
        return db.get(TestReport, report_id)

    # ------------------------------------------------------------------
    # GET BY MODULE
    # ------------------------------------------------------------------
    @staticmethod
    def get_by_module(db: Session, module_name: str) -> List[TestReport]:
        return db.exec(
            select(TestReport).where(TestReport.module_name == module_name)
        ).all()

    # ------------------------------------------------------------------
    # PARSE SCHEMATHESIS JSON REPORT FILE → dict ready for save_from_dict
    # ------------------------------------------------------------------
    @staticmethod
    def parse_schemathesis_file(report_path: str) -> dict:
        """
        Parse a Schemathesis JSON report file and return a normalised dict
        that can be passed directly to save_from_dict().
        """
        with open(report_path, "r") as f:
            data = json.load(f)

        checks = data.get("checks", [])
        total = len(checks)
        passed = sum(1 for c in checks if c.get("status") == "success")
        failed = total - passed
        failures = [
            {
                "name": c.get("name"),
                "message": c.get("message"),
                "status": c.get("status"),
            }
            for c in checks
            if c.get("status") != "success"
        ]

        return {
            "schemathesis": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "failures": failures,
                "errors": [],
            }
        }


test_report_service = TestReportService()
