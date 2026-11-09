from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.http import HttpResponse


def excel_report(fields, rows):
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.utils import get_column_letter

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Projects")
    sheet.freeze_panes = "A2"
    for column, field in enumerate(fields, 1):
        sheet.column_dimensions[get_column_letter(column)].width = max(16, len(field) + 3)
    sheet.append(fields)
    for row in rows:
        cells = []
        for field in fields:
            value = row[field]
            if field in {"approved_budget", "recorded_expenditure", "remaining", "variance"}:
                value = Decimal(value)
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = "s"
            cells.append(cell)
        sheet.append(cells)
    output = BytesIO()
    workbook.save(output)
    return download(
        output, "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def chart_bars(width, rows):
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib.colors import HexColor

    height = 20 * len(rows)
    drawing = Drawing(width, height)
    maximum = max(value for _, value, _ in rows) or 1
    bar_start = 115
    bar_width = width - bar_start - 170
    for index, (label, value, color) in enumerate(rows):
        y = height - (index + 1) * 20 + 5
        drawing.add(String(0, y + 1, label, fontName="Helvetica", fontSize=9, fillColor=HexColor("#202238")))
        drawing.add(Rect(bar_start, y, bar_width, 10, fillColor=HexColor("#edeaf7"), strokeColor=None))
        if value:
            drawing.add(Rect(
                bar_start, y, bar_width * float(value / maximum), 10,
                fillColor=HexColor(color), strokeColor=None,
            ))
        drawing.add(String(
            bar_start + bar_width + 9, y + 1, f"{value:,}",
            fontName="Helvetica", fontSize=9, fillColor=HexColor("#202238"),
        ))
    return drawing


def pdf_report(rows, charts):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), title="Project portfolio", topMargin=46, bottomMargin=46,
    )
    styles = getSampleStyleSheet()
    fields = ("title", "department", "status", "planned_end", "progress", "currency",
              "approved_budget", "recorded_expenditure", "remaining")
    titles = ("Project", "Department", "Status", "Due date", "Progress", "Currency",
              "Approved budget", "Recorded spend", "Remaining")
    table_rows = [titles]
    for row in rows:
        values = []
        for field in fields:
            value = row[field]
            if field == "progress" and value is not None:
                value = f"{value}% ({row['progress_source'].replace('_', ' ')})"
            elif field == "status":
                value = value.replace("_", " ").capitalize()
            elif field in {"approved_budget", "recorded_expenditure", "remaining"}:
                value = f"{Decimal(value):,.2f}"
            values.append(Paragraph(escape(str(value if value is not None else "—")), styles["BodyText"]))
        table_rows.append(values)
    table = LongTable(
        table_rows, repeatRows=1,
        colWidths=[document.width * fraction for fraction in (.17, .12, .09, .1, .1, .065, .115, .12, .12)],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eae6ff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    story = [
        Paragraph("Project portfolio", styles["Title"]),
        Paragraph(f"Projects: {len(table_rows) - 1}. Spending reflects recorded entries.", styles["Normal"]),
    ]
    if charts["status_counts"]:
        story.extend([
            Paragraph("Projects by status", styles["Heading2"]),
            chart_bars(document.width, [
                (status.replace("_", " ").capitalize(), count, "#5544ce")
                for status, count in charts["status_counts"].items()
            ]),
        ])
        for currency, totals in charts["spending"].items():
            story.extend([
                Paragraph(f"Budget and spending ({currency})", styles["Heading2"]),
                chart_bars(document.width, [
                    ("Approved budget", Decimal(totals["budget"]), "#5544ce"),
                    ("Recorded spending", Decimal(totals["recorded"]), "#1c8b84"),
                ]),
            ])
    document.build([*story, Spacer(1, 14), table])
    return download(output, "pdf", "application/pdf")


def download(output, extension, mime_type):
    response = HttpResponse(output.getvalue(), content_type=mime_type)
    response["Content-Disposition"] = f'attachment; filename="project-portfolio.{extension}"'
    return response
