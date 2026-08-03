from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponse
import os
from io import BytesIO
from django.utils import timezone

from accounts.models import UserModule
from registration.models import Student, StudentClassHistory
from academic.models import Result
from discipline.models import DisciplineCase
from .models import GraduateCollection
from academic.utils_notifications import notify_module_admins
from core.pdf_signing import sign_pdf_bytes

# For PDF generation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import cm
from django.conf import settings


def is_certificate_admin(user):
    """
    Checks if the user is a superuser or an admin of the certificate module.
    """
    if user.is_superuser:
        return True
    return UserModule.objects.filter(
        user=user,
        module__name='certificate',
        is_admin=True,
        is_approved=True
    ).exists()


def has_certificate_access(user):
    """
    Checks if the user is a superuser or has approved access to the certificate module.
    """
    if user.is_superuser:
        return True
    return UserModule.objects.filter(
        user=user,
        module__name='certificate',
        is_approved=True
    ).exists()


@login_required
def certificate_dashboard(request):
    """
    Dashboard for the Certificate module.
    """
    if not has_certificate_access(request.user):
        messages.error(request, "Access denied. You do not have access to the Certificate module.")
        return redirect('dashboard')

    graduates = Student.objects.filter(school_status='Graduated', is_archived=False)
    total_graduates = graduates.count()
    
    # Stats for the dashboard cards
    graduate_collections = GraduateCollection.objects.filter(student__school_status='Graduated', student__is_archived=False)
    both_collected = graduate_collections.filter(certificate_collected=True, result_slip_collected=True).count()
    cert_only = graduate_collections.filter(certificate_collected=True, result_slip_collected=False).count()
    result_only = graduate_collections.filter(certificate_collected=False, result_slip_collected=True).count()
    none_collected = total_graduates - graduate_collections.filter(Q(certificate_collected=True) | Q(result_slip_collected=True)).count()
    certificate_available = graduate_collections.filter(certificate_received_at_school=True, necta_certificate_no__isnull=False).exclude(necta_certificate_no='').count()
    result_slip_available = graduate_collections.filter(result_slip_received_at_school=True, necta_result_slip_no__isnull=False).exclude(necta_result_slip_no='').count()

    available_years = StudentClassHistory.objects.filter(
        to_class='Graduated'
    ).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    graduation_groups = StudentClassHistory.objects.filter(
        to_class='Graduated'
    ).values('academic_year', 'from_class').annotate(total=Count('id')).order_by('-academic_year', 'from_class')

    return render(request, 'certificate/dashboard.html', {
        'total_graduates': total_graduates,
        'both_collected': both_collected,
        'cert_only': cert_only,
        'result_only': result_only,
        'none_collected': none_collected,
        'certificate_available': certificate_available,
        'result_slip_available': result_slip_available,
        'available_years': available_years,
        'graduation_groups': graduation_groups,
    })


@login_required
def graduates_list(request):
    """
    A dedicated place to see all graduated students.
    Allows filtering by the year they graduated (Form 4 2026, Form 6 2027, etc.)
    """
    if not has_certificate_access(request.user):
        messages.error(request, "Access denied. Graduation records are for authorized staff only.")
        return redirect('dashboard')

    graduates = Student.objects.filter(school_status='Graduated', is_archived=False)

    selected_year = request.GET.get('year')
    selected_level = request.GET.get('level', '')
    selected_status = request.GET.get('status', '')

    if selected_year:
        graduation_filter = Q(class_history__to_class='Graduated', class_history__academic_year=selected_year)
        if selected_level:
            graduation_filter &= Q(class_history__from_class=selected_level)
        graduates = graduates.filter(graduation_filter).distinct()

    if selected_status:
        if selected_status == 'both':
            graduates = graduates.filter(collection_record__certificate_collected=True, collection_record__result_slip_collected=True)
        elif selected_status == 'cert':
            graduates = graduates.filter(collection_record__certificate_collected=True, collection_record__result_slip_collected=False)
        elif selected_status == 'result':
            graduates = graduates.filter(collection_record__certificate_collected=False, collection_record__result_slip_collected=True)
        elif selected_status == 'none':
            graduates = graduates.filter(
                Q(collection_record__isnull=True) | 
                (Q(collection_record__certificate_collected=False) & Q(collection_record__result_slip_collected=False))
            )
        elif selected_status == 'available':
            graduates = graduates.filter(
                Q(collection_record__certificate_received_at_school=True) |
                Q(collection_record__result_slip_received_at_school=True)
            )

    # Search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        graduates = graduates.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(registration_number__icontains=search_query)
        )

    # Get list of years where graduations occurred for the filter dropdown
    available_years = StudentClassHistory.objects.filter(
        to_class='Graduated'
    ).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    graduation_groups = StudentClassHistory.objects.filter(
        to_class='Graduated'
    ).values('academic_year', 'from_class').annotate(total=Count('id')).order_by('-academic_year', 'from_class')

    paginator = Paginator(graduates.select_related('collection_record').order_by('first_name'), 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    graduation_labels = {}
    for entry in StudentClassHistory.objects.filter(
        student__in=page_obj.object_list,
        to_class='Graduated'
    ).order_by('-changed_at'):
        graduation_labels.setdefault(entry.student_id, f"{entry.from_class} {entry.academic_year}")
    for student in page_obj.object_list:
        student.graduation_label = graduation_labels.get(student.id, 'Graduated')

    return render(request, 'certificate/graduates_list.html', {
        'page_obj': page_obj,
        'available_years': available_years,
        'graduation_groups': graduation_groups,
        'selected_year': selected_year,
        'selected_level': selected_level,
        'search_query': search_query,
        'selected_status': selected_status,
    })

@login_required
def mark_collection(request, student_id):
    """
    Updates whether the student has collected their certificate or result slip.
    """
    if not has_certificate_access(request.user):
        return redirect('dashboard')
    
    if request.method != 'POST':
        messages.error(request, "Document collection must be confirmed from the graduates list.")
        return redirect('certificate:graduates_list')

    student = get_object_or_404(Student, id=student_id, school_status='Graduated')
    collection, created = GraduateCollection.objects.get_or_create(student=student)
    
    doc_type = request.POST.get('type') 
    
    if doc_type == 'cert':
        if collection.certificate_collected:
            messages.info(request, f"Certificate was already marked collected for {student.first_name}.")
            return redirect('certificate:graduates_list')
        if not collection.certificate_available:
            messages.error(request, "Certificate cannot be collected until its NECTA number is recorded and marked received at school.")
            return redirect('certificate:graduates_list')
        collection.certificate_collected = True
    elif doc_type == 'result':
        if collection.result_slip_collected:
            messages.info(request, f"Result slip was already marked collected for {student.first_name}.")
            return redirect('certificate:graduates_list')
        if not collection.result_slip_available:
            messages.error(request, "Result slip cannot be collected until its NECTA number is recorded and marked received at school.")
            return redirect('certificate:graduates_list')
        collection.result_slip_collected = True
    else:
        messages.error(request, "Invalid collection type.")
        return redirect('certificate:graduates_list')
    
    collection.date_issued = timezone.now()
    collection.issued_by = request.user
    collection.save()
    
    messages.success(request, f"Documents issued to {student.first_name}. You can now print the collection receipt.")
    return redirect('certificate:graduates_list')


@login_required
def update_necta_details(request, student_id):
    """
    Allows admin to enter the official NECTA Certificate and Result Slip numbers.
    """
    if not has_certificate_access(request.user):
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id, school_status='Graduated')
    collection, created = GraduateCollection.objects.get_or_create(student=student)

    if request.method == 'POST':
        was_received = collection.is_received_at_school

        collection.necta_certificate_no = request.POST.get('cert_no', '').strip() or None
        collection.necta_result_slip_no = request.POST.get('result_no', '').strip() or None
        collection.certificate_received_at_school = request.POST.get('cert_received') == 'on'
        collection.result_slip_received_at_school = request.POST.get('result_received') == 'on'
        collection.is_received_at_school = collection.certificate_received_at_school and collection.result_slip_received_at_school
        collection.certificate_unavailable_reason = request.POST.get('cert_unavailable_reason', '').strip()
        collection.result_slip_unavailable_reason = request.POST.get('result_unavailable_reason', '').strip()
        collection.notes = request.POST.get('notes', '').strip()
        collection.save()

        if collection.is_received_at_school and not was_received:
            notify_module_admins(
                'certificate',
                f"Certificate and result slip for {student.registration_number} ({student.first_name} {student.last_name}) have arrived at school and are ready for collection.",
                email=True,
                email_subject="Documents ready for collection",
            )

        messages.success(request, f"NECTA details updated for {student.registration_number}")
        return redirect('certificate:graduates_list')

    return render(request, 'certificate/update_necta_details.html', {
        'student': student,
        'collection': collection
    })


@login_required
def student_full_history(request, student_id):
    """
    The 'Academic History' view. Shows results, discipline, and movements
    even after the student has graduated.
    """
    if not has_certificate_access(request.user):
        messages.error(request, "Access denied. Student history is for authorized staff only.")
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id)

    context = {
        'student': student,
        'academic_results': Result.objects.filter(student=student, exam__is_published=True).select_related('exam').order_by('-exam__created_at'),
        'discipline_records': DisciplineCase.objects.filter(student=student).order_by('-date_reported'),
        'class_history': student.class_history.all().order_by('-changed_at'),
    }
    return render(request, 'certificate/student_history.html', context)


@login_required
def generate_collection_receipt(request, student_id):
    """
    Generates an official Document Collection Receipt (Proof of Issuance).
    """
    if not has_certificate_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id, school_status='Graduated')

    collection = getattr(student, 'collection_record', None)

    # Built into a buffer first (not straight into the HTTP response) so it
    # can be digitally signed before being sent -- signing needs to read
    # back the complete PDF, which isn't possible once bytes are streamed out.
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()

    # Custom Styles for Certificate
    cert_title = ParagraphStyle('CertTitle', parent=styles['Heading1'], fontSize=24, alignment=1, textColor=colors.HexColor('#1e3a8a'), spaceAfter=20)
    cert_body = ParagraphStyle('CertBody', parent=styles['Normal'], fontSize=12, alignment=1, leading=18)
    cert_sub = ParagraphStyle('CertSub', parent=styles['Normal'], fontSize=16, alignment=1, fontName='Helvetica-Bold', spaceAfter=10)

    # School Header
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'school_logo.png')
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=3*cm, height=3*cm))
        elements.append(Spacer(1, 10))

    elements.append(Paragraph("DODOMA SECONDARY SCHOOL", cert_sub))
    elements.append(Paragraph("DOCUMENT COLLECTION RECEIPT (NECTA)", cert_title))
    elements.append(Spacer(1, 20))

    # Student Information
    full_name = f"{student.first_name} {student.middle_name or ''} {student.last_name or ''}".upper()
    elements.append(Paragraph(f"This is to certify that", cert_body))
    elements.append(Paragraph(full_name, cert_title))
    elements.append(Paragraph(f"Registration Number: {student.registration_number}", cert_body))

    # History Logic
    first_year = student.date_of_admission.year if student.date_of_admission else "N/A"
    last_history = student.class_history.filter(to_class='Graduated').first()
    grad_year = last_history.academic_year if last_history else "N/A"

    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        f"Has successfully completed their studies at Dodoma School from year {first_year} to {grad_year}. "
        f"During their tenure, the student was enrolled in {student.get_student_class_display()} "
        f"and showed dedicated commitment to the school curriculum.", cert_body))

    # Discipline/Conduct Summary
    # Assuming get_discipline_score() exists on Student model
    discipline_score = student.get_discipline_score() if hasattr(student, 'get_discipline_score') else 0
    conduct = "EXCELLENT" if discipline_score == 0 else "GOOD" if discipline_score < 5 else "SATISFACTORY"
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(f"GENERAL CONDUCT: {conduct}", cert_sub))

    # Signatures
    elements.append(Spacer(1, 50))
    sig_data = [
        [Paragraph("__________________________", cert_body), "", Paragraph("__________________________", cert_body)],
        [Paragraph("SCHOOL PRINCIPAL", cert_body), "", Paragraph("DATE OF ISSUE", cert_body)]
    ]
    sig_table = Table(sig_data, colWidths=[8*cm, 4*cm, 8*cm])
    elements.append(sig_table)

    doc.build(elements)

    pdf_bytes = sign_pdf_bytes(
        buffer.getvalue(),
        reason='Official document collection receipt',
        location='Dodoma Secondary School, Tanzania',
    )

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Collection_Receipt_{student.registration_number}.pdf"'
    return response
