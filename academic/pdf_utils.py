from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from .utils import calculate_student_result


styles = getSampleStyleSheet()


# ===============================
# SINGLE STUDENT PDF
# ===============================
def generate_student_pdf(response, student, exam):

    doc = SimpleDocTemplate(response)

    elements = []

    result = calculate_student_result(student, exam)

    # HEADER
    elements.append(Paragraph("SCHOOL NAME", styles['Title']))
    elements.append(Paragraph("Academic Result Slip", styles['Heading2']))
    elements.append(Spacer(1, 10))

    # STUDENT INFO
    elements.append(Paragraph(f"Name: {student.first_name} {student.last_name}", styles['Normal']))
    elements.append(Paragraph(f"Class: {student.student_class}", styles['Normal']))
    elements.append(Paragraph(f"Exam: {exam.name}", styles['Normal']))

    elements.append(Spacer(1, 10))

    # TABLE DATA
    data = [["Subject", "Grade"]]

    for s in result["subjects"]:
        data.append([s["subject"].name, s["grade"]])

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

        elements.append(Paragraph("SCHOOL NAME", styles['Title']))
        elements.append(Paragraph("Academic Result Slip", styles['Heading2']))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(f"Name: {student.first_name} {student.last_name}", styles['Normal']))
        elements.append(Paragraph(f"Class: {student.student_class}", styles['Normal']))
        elements.append(Paragraph(f"Exam: {exam.name}", styles['Normal']))

        elements.append(Spacer(1, 10))

        data = [["Subject", "Grade"]]

        for s in result["subjects"]:
            data.append([s["subject"].name, s["grade"]])

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