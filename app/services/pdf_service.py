from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


@dataclass
class ReportContent:
    report_title: str
    start_date: str
    end_date: str
    generated_at: str
    summary: dict
    customer_rows: list[tuple[str, int, float]]


def build_pdf(report_path: Path, content: ReportContent) -> None:
    doc = SimpleDocTemplate(
        str(report_path),  # ReportLab 4.x requires str, not pathlib.Path
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.alignment = 1
    normal_style = styles["BodyText"]
    summary_style = ParagraphStyle(
        name="Summary",
        parent=styles["BodyText"],
        spaceAfter=12,
    )

    story = [
        Paragraph(content.report_title, title_style),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Report period: {content.start_date} to {content.end_date}", normal_style),
        Paragraph(f"Generated at: {content.generated_at}", normal_style),
        Spacer(1, 0.25 * inch),
        Paragraph("Summary", styles["Heading2"]),
        Spacer(1, 0.1 * inch),
    ]

    summary_lines = [
        f"Total orders: {content.summary['order_count']}",
        f"Total revenue: ${content.summary['total_amount']:.2f}",
        f"Average order value: ${content.summary['average_order_value']:.2f}",
        f"Unique customers: {content.summary['unique_customers']}",
    ]
    for line in summary_lines:
        story.append(Paragraph(line, summary_style))

    story.extend([
        Spacer(1, 0.25 * inch),
        Paragraph("Orders by customer", styles["Heading2"]),
        Spacer(1, 0.1 * inch),
    ])

    table_data = [("Customer", "Order Count", "Total Amount")]
    table_data += [
        (row["customer_name"], str(row["order_count"]), f"${row['total_amount']:.2f}")
        for row in content.customer_rows
    ]

    table = Table(table_data, hAlign="LEFT", colWidths=[2.75 * inch, 1.5 * inch, 2.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)

    doc.build(story)
