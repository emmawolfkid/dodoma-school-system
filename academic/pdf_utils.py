from pathlib import Path

from django.conf import settings
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from .utils import calculate_student_result


styles = getSampleStyleSheet()


def add_pdf_header(elements, title):
    logo_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'school_logo.png'
    if logo_path.exists():
        elements.append(Image(str(logo_path), width=54, height=54))
    elements.append(Paragraph("DODOMA SECONDARY SCHOOL", styles['Title']))
    elements.append(Paragraph(title, styles['Heading2']))
    elements.append(Spacer(1, 10))


# ===============================
# SINGLE STUDENT PDF
# ===============================
def generate_student_pdf(response, student, exam):

    doc = SimpleDocTemplate(response)

    elements = []

    result = calculate_student_result(student, exam)

    add_pdf_header(elements, "Academic Result Slip")

    # STUDENT INFO
    elements.append(Paragraph(f"Name: {student.first_name} {student.last_name}", styles['Normal']))
    elements.append(Paragraph(f"Class: {student.student_class}", styles['Normal']))
    elements.append(Paragraph(f"Exam: {exam.name}", styles['Normal']))

    elements.append(Spacer(1, 10))

    # TABLE DATA
    data = [["Subject", "Marks", "Grade"]]

    for s in result["subjects"]:
        marks = "ABS" if s["grade"] == "ABS" else s.get("total_marks", "-")
        data.append([s["subject"].name, marks, s["grade"]])

    table = Table(data)
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
    ]))

    elements.append(table)

    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"Division: {result['division']}", styles['Heading3']))
    elements.append(Paragraph(f"Points: {result['total_points']}", styles['Normal']))

    doc.build(elements)


# ===============================
# CLASS PDF (ALL STUDENTS)
# ===============================
def generate_class_pdf(response, students, exam):

    doc = SimpleDocTemplate(response)

    elements = []

    for student in students:

        result = calculate_student_result(student, exam)

        add_pdf_header(elements, "Academic Result Slip")

        elements.append(Paragraph(f"Name: {student.first_name} {student.last_name}", styles['Normal']))
        elements.append(Paragraph(f"Class: {student.student_class}", styles['Normal']))
        elements.append(Paragraph(f"Exam: {exam.name}", styles['Normal']))

        elements.append(Spacer(1, 10))

        data = [["Subject", "Marks", "Grade"]]

        for s in result["subjects"]:
            marks = "ABS" if s["grade"] == "ABS" else s.get("total_marks", "-")
            data.append([s["subject"].name, marks, s["grade"]])

        table = Table(data)
        table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ]))

        elements.append(table)

        elements.append(Spacer(1, 10))

        elements.append(Paragraph(f"Division: {result['division']}", styles['Heading3']))
        elements.append(Paragraph(f"Points: {result['total_points']}", styles['Normal']))

        elements.append(PageBreak())

    doc.build(elements)
