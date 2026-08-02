from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from .utils import calculate_student_result


styles = getSampleStyleSheet()

PRIMARY = colors.HexColor('#1a3c6e')
HEADER_TEXT = colors.white
MUTED = colors.HexColor('#667085')

GRADE_COLORS = {
    'A': colors.HexColor('#dcfce7'),
    'B': colors.HexColor('#dbeafe'),
    'C': colors.HexColor('#e0f2fe'),
    'D': colors.HexColor('#fef3c7'),
    'E': colors.HexColor('#ffedd5'),
    'S': colors.HexColor('#ffedd5'),
    'F': colors.HexColor('#fee2e2'),
    'ABS': colors.HexColor('#fee2e2'),
}

title_style = ParagraphStyle('SchoolTitle', parent=styles['Title'], textColor=PRIMARY, alignment=TA_CENTER)
subtitle_style = ParagraphStyle('SchoolSubtitle', parent=styles['Heading2'], textColor=colors.HexColor('#2557a7'), alignment=TA_CENTER)
meta_style = ParagraphStyle('Meta', parent=styles['Normal'], textColor=MUTED, alignment=TA_CENTER, fontSize=9)
division_style = ParagraphStyle('Division', parent=styles['Heading2'], textColor=PRIMARY)
signature_style = ParagraphStyle('Signature', parent=styles['Normal'], alignment=TA_CENTER, textColor=MUTED, fontSize=8)


def add_pdf_header(elements, title):
    logo_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'school_logo.png'
    if logo_path.exists():
        img = Image(str(logo_path), width=54, height=54)
        img.hAlign = 'CENTER'
        elements.append(img)
    elements.append(Paragraph("DODOMA SECONDARY SCHOOL", title_style))
    elements.append(Paragraph(title, subtitle_style))
    elements.append(Paragraph(f"Generated {timezone.now().strftime('%d %b %Y, %H:%M')}", meta_style))
    elements.append(Spacer(1, 12))


def build_result_table(result):
    data = [["Subject", "Marks", "Grade"]]
    grade_rows = []

    for i, s in enumerate(result["subjects"], start=1):
        marks = "ABS" if s["grade"] == "ABS" else s.get("total_marks", "-")
        data.append([s["subject"].name, marks, s["grade"]])
        grade_rows.append((i, s["grade"]))

    table = Table(data, colWidths=[260, 100, 100])
    table_style = [
        ('GRID', (0, 0), (-1, -1), 0.75, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_TEXT),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (0, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]
    for row, grade in grade_rows:
        bg = GRADE_COLORS.get(grade)
        if bg:
            table_style.append(('BACKGROUND', (2, row), (2, row), bg))
            table_style.append(('FONTNAME', (2, row), (2, row), 'Helvetica-Bold'))
    table.setStyle(TableStyle(table_style))
    return table


def add_signature_footer(elements):
    elements.append(Spacer(1, 28))
    footer = Table(
        [[
            Paragraph("_______________________<br/>Class Teacher", signature_style),
            Paragraph("_______________________<br/>Academic Coordinator", signature_style),
            Paragraph("_______________________<br/>Head of School", signature_style),
        ]],
        colWidths=[160, 160, 160],
    )
    elements.append(footer)


# ===============================
# SINGLE STUDENT PDF
# ===============================
def generate_student_pdf(response, student, exam):

    doc = SimpleDocTemplate(response, topMargin=40, bottomMargin=40)

    elements = []

    result = calculate_student_result(student, exam)

    add_pdf_header(elements, "Academic Result Slip")

    elements.append(Paragraph(f"<b>Name:</b> {student.first_name} {student.last_name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Registration No.:</b> {student.registration_number}", styles['Normal']))
    elements.append(Paragraph(f"<b>Class:</b> {student.student_class}", styles['Normal']))
    elements.append(Paragraph(f"<b>Exam:</b> {exam.name} ({exam.academic_year.year})", styles['Normal']))

    elements.append(Spacer(1, 12))
    elements.append(build_result_table(result))
    elements.append(Spacer(1, 14))

    elements.append(Paragraph(f"Division: {result['division']}", division_style))
    elements.append(Paragraph(f"Total Points: {result['total_points']}", styles['Normal']))

    add_signature_footer(elements)

    doc.build(elements)


# ===============================
# CLASS PDF (ALL STUDENTS)
# ===============================
def generate_class_pdf(response, students, exam):

    doc = SimpleDocTemplate(response, topMargin=40, bottomMargin=40)

    elements = []

    for i, student in enumerate(students):

        result = calculate_student_result(student, exam)

        add_pdf_header(elements, "Academic Result Slip")

        elements.append(Paragraph(f"<b>Name:</b> {student.first_name} {student.last_name}", styles['Normal']))
        elements.append(Paragraph(f"<b>Registration No.:</b> {student.registration_number}", styles['Normal']))
        elements.append(Paragraph(f"<b>Class:</b> {student.student_class}", styles['Normal']))
        elements.append(Paragraph(f"<b>Exam:</b> {exam.name} ({exam.academic_year.year})", styles['Normal']))

        elements.append(Spacer(1, 12))
        elements.append(build_result_table(result))
        elements.append(Spacer(1, 14))

        elements.append(Paragraph(f"Division: {result['division']}", division_style))
        elements.append(Paragraph(f"Total Points: {result['total_points']}", styles['Normal']))

        add_signature_footer(elements)

        if i < len(students) - 1:
            elements.append(PageBreak())

    doc.build(elements)
