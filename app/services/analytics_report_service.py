from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZIP_DEFLATED, ZipFile

from jose import JWTError, jwt
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import settings
from app.core.database import engine
from app.core.public_url import to_public_url
from app.models.analytics_dashboard import AnalyticsReportJob
from app.repositories.analytics_dashboard_repository import AnalyticsDashboardRepository
from app.services.analytics_dashboard_service import AnalyticsDashboardService, REPORT_SECTION_VALUES, normalize_utc_naive


REPORT_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "reports"


def _ensure_report_root() -> Path:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    return REPORT_ROOT


def _make_report_filename(report_id: str, report_format: str) -> str:
    extension = report_format.lower()
    return f"{report_id}.{extension}"


def _flatten_payload_for_rows(payload: dict[str, Any], section: str, value: Any, rows: list[list[str]], prefix: str = "") -> None:
    key_prefix = f"{prefix}." if prefix else ""
    if isinstance(value, dict):
        for key, nested in value.items():
            _flatten_payload_for_rows(payload, section, nested, rows, prefix=f"{key_prefix}{key}")
        return
    if isinstance(value, list):
        for idx, nested in enumerate(value):
            _flatten_payload_for_rows(payload, section, nested, rows, prefix=f"{key_prefix}{idx}")
        return
    if isinstance(value, (datetime,)):
        rendered = value.isoformat()
    elif isinstance(value, Decimal):
        rendered = str(value)
    else:
        rendered = "" if value is None else str(value)
    rows.append([section, prefix, rendered])


def _payload_to_rows(payload: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = [["section", "field", "value"]]
    for section, section_value in payload.items():
        _flatten_payload_for_rows(payload, str(section), section_value, rows)
    return rows


def _render_csv_bytes(payload: dict[str, Any]) -> bytes:
    rows = _payload_to_rows(payload)
    lines = [",".join(json.dumps(cell, ensure_ascii=False) for cell in row) for row in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _xlsx_col_name(index: int) -> str:
    letters = ""
    col = index + 1
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _render_xlsx_bytes(payload: dict[str, Any]) -> bytes:
    rows = _payload_to_rows(payload)
    sheet_rows: list[str] = []
    for row_idx, row in enumerate(rows, start=1):
        cells_xml: list[str] = []
        for col_idx, cell in enumerate(row):
            cell_ref = f"{_xlsx_col_name(col_idx)}{row_idx}"
            cell_text = xml_escape(str(cell))
            cells_xml.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{cell_text}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_idx}">{"".join(cells_xml)}</row>')

    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Dashboard" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        "</styleSheet>"
    )

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
        archive.writestr("xl/styles.xml", styles_xml)
    return output.getvalue()


def _humanize_label(label: str) -> str:
    return label.replace("_", " ").replace("-", " ").strip().title()


def _render_pdf_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,d}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _render_pdf_bytes(payload: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="WEZU Logistics Dashboard Report",
        author="WEZU Logistics",
    )
    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "Brand",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        textColor=colors.HexColor("#0B3D91"),
        leading=20,
        spaceAfter=2,
    )
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#1A202C"),
        leading=16,
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#1A202C"),
        leading=14,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#2D3748"),
        leading=12,
    )
    small_muted_style = ParagraphStyle(
        "SmallMuted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#4A5568"),
        leading=10,
    )
    metadata_label_style = ParagraphStyle(
        "MetadataLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#1A202C"),
        leading=11,
    )
    metadata_value_style = ParagraphStyle(
        "MetadataValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#1A202C"),
        leading=11,
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=colors.white,
        leading=10.5,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#2D3748"),
        leading=10.5,
        wordWrap="CJK",
    )

    def _soft_wrap_long_tokens(text: str, *, token_chunk: int = 24) -> str:
        wrapped_tokens: list[str] = []
        for token in text.split(" "):
            if len(token) <= token_chunk:
                wrapped_tokens.append(token)
                continue
            chunks = [token[i : i + token_chunk] for i in range(0, len(token), token_chunk)]
            wrapped_tokens.append("\u200b".join(chunks))
        return " ".join(wrapped_tokens)

    def _to_table_paragraph(value: Any, style: ParagraphStyle, *, max_chars: int | None = None) -> Paragraph:
        text_value = _render_pdf_value(value)
        if max_chars and len(text_value) > max_chars:
            text_value = f"{text_value[: max_chars - 1]}…"
        normalized = _soft_wrap_long_tokens(text_value.replace("\r\n", "\n").replace("\r", "\n"))
        escaped = xml_escape(normalized).replace("\n", "<br/>")
        return Paragraph(escaped, style)

    story: list[Any] = []
    generated_at_utc = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    report_from = _render_pdf_value(payload.get("from"))
    report_to = _render_pdf_value(payload.get("to"))
    timezone_name = _render_pdf_value(payload.get("timezone"))

    story.append(Paragraph("WEZU Logistics", brand_style))
    story.append(Paragraph("Dashboard Analytics Report", title_style))
    story.append(Spacer(1, 2 * mm))

    metadata_rows = [
        [
            _to_table_paragraph("Generated (UTC)", metadata_label_style),
            _to_table_paragraph(generated_at_utc, metadata_value_style),
        ],
        [
            _to_table_paragraph("Date Range", metadata_label_style),
            _to_table_paragraph(f"{report_from} to {report_to}", metadata_value_style),
        ],
        [
            _to_table_paragraph("Timezone", metadata_label_style),
            _to_table_paragraph(timezone_name, metadata_value_style),
        ],
    ]
    metadata_table = Table(metadata_rows, colWidths=[34 * mm, doc.width - 34 * mm])
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF2F7")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1A202C")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E0")),
            ]
        )
    )
    story.append(metadata_table)
    story.append(Spacer(1, 5 * mm))

    kpis = payload.get("kpis") if isinstance(payload.get("kpis"), dict) else {}
    if kpis:
        story.append(Paragraph("KPI Summary", section_title_style))
        ordered_kpis = list(kpis.items())
        card_columns = 3
        card_gap = 3 * mm
        card_width = (doc.width - card_gap * (card_columns - 1)) / card_columns
        card_cells: list[Paragraph] = []
        for key, value in ordered_kpis:
            card_text = (
                f"<font color='#4A5568' size='8'>{_humanize_label(str(key))}</font><br/>"
                f"<font color='#1A202C' size='12'><b>{_render_pdf_value(value)}</b></font>"
            )
            card_cells.append(Paragraph(card_text, body_style))

        rows: list[list[Any]] = []
        for idx in range(0, len(card_cells), card_columns):
            row = card_cells[idx : idx + card_columns]
            while len(row) < card_columns:
                row.append(Paragraph("", body_style))
            rows.append(row)
        cards_table = Table(rows, colWidths=[card_width] * card_columns, hAlign="LEFT")
        card_style: list[tuple[Any, ...]] = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D6DEE8")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C7D2E0")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
        ]
        for col_idx in range(card_columns - 1):
            card_style.append(("RIGHTPADDING", (col_idx, 0), (col_idx, -1), 8 + card_gap))
        cards_table.setStyle(TableStyle(card_style))
        story.append(cards_table)
        story.append(Spacer(1, 5 * mm))

    def _append_zebra_table(headers: list[str], data_rows: list[list[Any]], widths: list[float]) -> None:
        if not data_rows:
            story.append(Paragraph("No data available.", small_muted_style))
            story.append(Spacer(1, 2 * mm))
            return

        header_cells = [_to_table_paragraph(_humanize_label(header), table_header_style) for header in headers]
        body_rows = [[_to_table_paragraph(cell, table_cell_style) for cell in row] for row in data_rows]
        rows = [header_cells] + body_rows
        table = Table(rows, colWidths=widths, repeatRows=1)
        style_entries: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E0")),
        ]
        for row_idx in range(1, len(rows)):
            if row_idx % 2 == 0:
                style_entries.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#F7FAFC")))
        table.setStyle(TableStyle(style_entries))
        story.append(table)
        story.append(Spacer(1, 3 * mm))

    section_order = ["recent_activity", "orders", "inventory", "fleet"]
    for section_name in section_order:
        section_data = payload.get(section_name)
        if not section_data:
            continue

        story.append(Paragraph(_humanize_label(section_name), section_title_style))
        if section_name == "recent_activity" and isinstance(section_data, dict):
            items = section_data.get("items") if isinstance(section_data.get("items"), list) else []
            rows = []
            for item in items[:40]:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    [
                        item.get("type", ""),
                        item.get("title", ""),
                        item.get("timestamp", ""),
                        item.get("reference_id", ""),
                    ]
                )
            _append_zebra_table(
                headers=["Type", "Title", "Timestamp", "Reference"],
                data_rows=rows,
                widths=[28 * mm, 78 * mm, 34 * mm, 34 * mm],
            )
            total = section_data.get("total", len(rows))
            story.append(Paragraph(f"Total events in window: <b>{_render_pdf_value(total)}</b>", small_muted_style))
            story.append(Spacer(1, 2 * mm))
            continue

        if section_name == "orders" and isinstance(section_data, dict):
            story.append(Paragraph(f"Total Orders: <b>{_render_pdf_value(section_data.get('total_orders'))}</b>", body_style))
            pipeline = section_data.get("pipeline_split") if isinstance(section_data.get("pipeline_split"), dict) else {}
            rows = [[_humanize_label(str(status)), count] for status, count in pipeline.items()]
            _append_zebra_table(headers=["Order Status", "Count"], data_rows=rows, widths=[doc.width * 0.7, doc.width * 0.3])
            continue

        if section_name == "inventory" and isinstance(section_data, dict):
            story.append(
                Paragraph(
                    f"Inventory Audit Count: <b>{_render_pdf_value(section_data.get('inventory_audit_count'))}</b>",
                    body_style,
                )
            )
            transfer_split = (
                section_data.get("transfer_split")
                if isinstance(section_data.get("transfer_split"), dict)
                else {}
            )
            rows = [[_humanize_label(str(status)), count] for status, count in transfer_split.items()]
            _append_zebra_table(headers=["Transfer Status", "Count"], data_rows=rows, widths=[doc.width * 0.7, doc.width * 0.3])
            continue

        if section_name == "fleet" and isinstance(section_data, dict):
            story.append(
                Paragraph(
                    f"Issue Count: <b>{_render_pdf_value(section_data.get('issue_count'))}</b> | "
                    f"Battery Swapped Events: <b>{_render_pdf_value(section_data.get('battery_swapped_events'))}</b>",
                    body_style,
                )
            )
            health_rows: list[list[Any]] = []
            for item in section_data.get("battery_health_distribution", []):
                if not isinstance(item, dict):
                    continue
                health_rows.append([item.get("label", ""), item.get("value", 0)])
            _append_zebra_table(headers=["Health Bucket", "Count"], data_rows=health_rows, widths=[doc.width * 0.7, doc.width * 0.3])
            continue

        if isinstance(section_data, dict):
            rows = [[_humanize_label(str(key)), _render_pdf_value(value)] for key, value in section_data.items()]
            _append_zebra_table(headers=["Field", "Value"], data_rows=rows, widths=[doc.width * 0.35, doc.width * 0.65])
        else:
            story.append(Paragraph(_render_pdf_value(section_data), body_style))
            story.append(Spacer(1, 2 * mm))

    def _draw_footer(canvas, report_doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D3DCE6"))
        canvas.setLineWidth(0.5)
        canvas.line(report_doc.leftMargin, 12 * mm, A4[0] - report_doc.rightMargin, 12 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#4A5568"))
        canvas.drawString(report_doc.leftMargin, 8 * mm, "WEZU Logistics")
        canvas.drawRightString(A4[0] - report_doc.rightMargin, 8 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return output.getvalue()


def _render_report_bytes(payload: dict[str, Any], report_format: str) -> bytes:
    normalized_format = report_format.lower()
    if normalized_format == "csv":
        return _render_csv_bytes(payload)
    if normalized_format == "xlsx":
        return _render_xlsx_bytes(payload)
    if normalized_format == "pdf":
        return _render_pdf_bytes(payload)
    raise ValueError(f"Unsupported report format '{report_format}'")


class AnalyticsReportService:
    DOWNLOAD_TOKEN_TYPE = "analytics_report_download"

    @staticmethod
    def create_download_token(report_id: str, *, expires_at: Optional[datetime] = None) -> str:
        token_expiry = expires_at
        if token_expiry is None or token_expiry <= datetime.utcnow():
            token_expiry = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "type": AnalyticsReportService.DOWNLOAD_TOKEN_TYPE,
            "rid": report_id,
            "exp": token_expiry,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def is_valid_download_token(token: str, *, report_id: str) -> bool:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            return False
        if payload.get("type") != AnalyticsReportService.DOWNLOAD_TOKEN_TYPE:
            return False
        return str(payload.get("rid") or "") == str(report_id)

    @staticmethod
    def build_download_url(report_id: str, *, expires_at: Optional[datetime] = None) -> str:
        token = AnalyticsReportService.create_download_token(report_id, expires_at=expires_at)
        return to_public_url(f"/api/v1/analytics/reports/{report_id}/download?token={token}")

    @staticmethod
    def queue_dashboard_report(
        session: Session,
        *,
        report_id: str,
        from_dt: datetime,
        to_dt: datetime,
        timezone_name: str,
        report_format: str,
        include_sections: Sequence[str],
        requested_by_user_id: Optional[int],
    ) -> AnalyticsReportJob:
        from_utc = normalize_utc_naive(from_dt)
        to_utc = normalize_utc_naive(to_dt)
        if from_utc is None or to_utc is None:
            raise ValueError("Report window cannot be empty")
        include = [section for section in include_sections if section in REPORT_SECTION_VALUES]
        job = AnalyticsReportJob(
            report_id=report_id,
            status="queued",
            report_format=report_format.lower(),
            timezone=timezone_name,
            include_sections=json.dumps(include),
            from_utc=from_utc,
            to_utc=to_utc,
            requested_by_user_id=requested_by_user_id,
            updated_at=datetime.utcnow(),
        )
        return AnalyticsDashboardRepository.create_report_job(session, job)

    @staticmethod
    def run_dashboard_report_job(
        report_id: str,
        db_engine: Engine | None = None,
    ) -> None:
        bound_engine = engine if db_engine is None else db_engine
        with Session(bound_engine) as session:
            job = AnalyticsDashboardRepository.get_report_job(session, report_id)
            if job is None:
                return
            AnalyticsDashboardRepository.update_report_job(
                session,
                report_id=report_id,
                status="processing",
                started_at=datetime.utcnow(),
                detail=None,
            )

        try:
            with Session(bound_engine) as session:
                job = AnalyticsDashboardRepository.get_report_job(session, report_id)
                if job is None:
                    return

                include_sections = json.loads(job.include_sections or "[]")
                if not isinstance(include_sections, list):
                    include_sections = list(REPORT_SECTION_VALUES)

                payload = AnalyticsDashboardService.build_report_sections(
                    session,
                    from_utc=job.from_utc,
                    to_utc=job.to_utc,
                    timezone_name=job.timezone,
                    include_sections=include_sections,
                )

                file_bytes = _render_report_bytes(payload, job.report_format)
                report_dir = _ensure_report_root()
                filename = _make_report_filename(job.report_id, job.report_format)
                file_path = report_dir / filename
                file_path.write_bytes(file_bytes)

                expires_at = datetime.utcnow() + timedelta(days=7)
                file_url = AnalyticsReportService.build_download_url(job.report_id, expires_at=expires_at)
                AnalyticsDashboardRepository.update_report_job(
                    session,
                    report_id=job.report_id,
                    status="completed",
                    file_path=str(file_path),
                    file_url=file_url,
                    expires_at=expires_at,
                    completed_at=datetime.utcnow(),
                    detail=None,
                )
        except Exception as exc:
            detail_message = str(exc) or repr(exc)
            with Session(bound_engine) as session:
                AnalyticsDashboardRepository.update_report_job(
                    session,
                    report_id=report_id,
                    status="failed",
                    completed_at=datetime.utcnow(),
                    detail=detail_message,
                )

    @staticmethod
    def get_report_status(session: Session, report_id: str) -> AnalyticsReportJob:
        job = AnalyticsDashboardRepository.get_report_job(session, report_id)
        if job is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Report not found")
        return job

    @staticmethod
    def read_report_file(job: AnalyticsReportJob) -> bytes:
        from fastapi import HTTPException

        if job.status != "completed":
            raise HTTPException(status_code=409, detail="Report is not ready yet")
        if not job.file_path:
            raise HTTPException(status_code=404, detail="Report file path is missing")
        path = Path(job.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Report file not found")
        return path.read_bytes()
