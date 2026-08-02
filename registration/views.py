from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, date, timedelta

# Re-add necessary imports that were removed but are still used in other functions
from accounts.models import UserModule, Module, User
from html import escape # Still used in normalize_header
import io # Still used in download_students_pdf
from .models import Student, Equipment, StudentClassHistory, PromotionBatch
from .forms import StudentForm
from .utils import has_permission
from audit.services import log_action


CLASS_ORDER = ['Form 1', 'Form 2', 'Form 3', 'Form 4', 'Form 5', 'Form 6']


def normalize_header(value):
    return str(value or '').strip().lower().replace('_', ' ').replace('-', ' ')


def normalize_class(value):
    raw = str(value or '').strip().lower().replace('-', ' ')
    compact = raw.replace(' ', '')
    class_map = {
        'form1': 'Form 1', '1': 'Form 1',
        'form2': 'Form 2', '2': 'Form 2',
        'form3': 'Form 3', '3': 'Form 3',
        'form4': 'Form 4', '4': 'Form 4',
        'form5': 'Form 5', '5': 'Form 5',
        'form6': 'Form 6', '6': 'Form 6',
    }
    return class_map.get(compact, str(value or '').strip())


def normalize_gender(value):
    raw = str(value or '').strip().lower()
    if raw in ['m', 'male']:
        return 'Male'
    if raw in ['f', 'female']:
        return 'Female'
    return str(value or '').strip()


def normalize_status(value, default='Active'):
    raw = str(value or default).strip().title()
    allowed = dict(Student.SCHOOL_STATUS_CHOICES)
    return raw if raw in allowed else default


def normalize_health(value, default='Fit'):
    raw = str(value or default).strip().title()
    allowed = dict(Student.HEALTH_CHOICES)
    return raw if raw in allowed else default


def parse_excel_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=value)).date()
    if isinstance(value, str):
        cleaned = value.strip()
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y']:
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                pass
    return None


def get_cell(sheet, row_num, column_position, field):
    col = column_position.get(field)
    if not col:
        return None
    return sheet.cell(row=row_num, column=col).value

# Ã°Å¸â€Â¥ CENTRAL PERMISSION SYSTEM (VERY IMPORTANT)
# has_permission() now lives solely in registration/utils.py (imported
# above) so there's only one copy of this authorization logic to maintain.


def is_registration_admin(user):
    if user.is_superuser:
        return True

    return has_permission(user, 'add') and UserModule.objects.filter(
        user=user,
        module__name='registration',
        is_admin=True,
        is_approved=True
    ).exists()


# ================= ADMIN =================

@login_required
def registration_admin_dashboard(request):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    module = Module.objects.get(name='registration')

    pending_users = UserModule.objects.filter(
        module=module,
        is_approved=False
    )

    return render(request, 'registration/admin/dashboard.html', {
        'pending_users': pending_users
    })


@login_required
def approve_user_registration(request, usermodule_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    user_module = get_object_or_404(UserModule, id=usermodule_id)
    user_module.is_approved = True
    user_module.save()

    return redirect('registration_admin_dashboard')


@login_required
def manage_registration_users(request):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    users = UserModule.objects.filter(module__name='registration')

    return render(request, 'registration/admin/users.html', {
        'users': users
    })


@login_required
def toggle_permission(request, usermodule_id, perm):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    um = get_object_or_404(UserModule, id=usermodule_id)

    if perm == 'add':
        um.can_add = not um.can_add
    elif perm == 'edit':
        um.can_edit = not um.can_edit
    elif perm == 'delete':
        um.can_delete = not um.can_delete

    um.save()

    return redirect('manage_registration_users')


@login_required
def make_registration_admin(request, usermodule_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    um = get_object_or_404(UserModule, id=usermodule_id)
    um.is_admin = True
    um.is_approved = True
    um.save()

    return redirect('manage_registration_users')


@login_required
def remove_registration_admin(request, usermodule_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')
    
    um = get_object_or_404(UserModule, id=usermodule_id)
    um.is_admin = False
    um.save()
    messages.success(request, f"Admin privileges removed from {um.user.username}")
    return redirect('manage_registration_users')


@login_required
def remove_user_from_module(request, usermodule_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')
    
    um = get_object_or_404(UserModule, id=usermodule_id)
    username = um.user.username
    um.delete()
    messages.success(request, f"User {username} removed from registration module")
    return redirect('manage_registration_users')


@login_required
def reset_user_password(request, user_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)

    temp_password = get_random_string(12)
    user.password = make_password(temp_password)
    user.must_change_password = True
    user.save()

    log_action(
        user=request.user,
        action='update',
        instance=user,
        module='registration',
        changes={
            'event': 'password_reset',
            'target_user': user.username,
            'must_change_password': True,
        }
    )

    messages.success(
        request,
        f"Password reset for {user.username}. Temporary password: {temp_password} "
        f"(they will be required to change it on next login)."
    )

    return redirect('manage_registration_users')


@login_required
def manage_equipment(request):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            # Ã°Å¸â€Â¥ STEP 7 Ã¢â‚¬â€ ADD EQUIPMENT WITH LOG
            equipment = Equipment.objects.create(name=name)
            
            log_action(
                user=request.user,
                action='create',
                instance=equipment,
                module='registration',
                changes={
                    "equipment": name
                }
            )

    equipments = Equipment.objects.all()

    return render(request, 'registration/admin/equipment.html', {
        'equipments': equipments
    })


@login_required
def edit_equipment(request, equipment_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')
    
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    if request.method == 'POST':
        new_name = request.POST.get('name')
        if new_name:
            equipment.name = new_name
            equipment.save()
            
            # Ã°Å¸â€Â¥ STEP 8 Ã¢â‚¬â€ EDIT EQUIPMENT LOG
            log_action(
                user=request.user,
                action='update',
                instance=equipment,
                module='registration',
                changes={
                    "new_name": equipment.name
                }
            )
    
    return redirect('manage_equipment')


@login_required
def delete_equipment(request, equipment_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')
    
    equipment = get_object_or_404(Equipment, id=equipment_id)
    equipment_name = equipment.name  # Store before delete
    equipment.delete()
    
    # Ã°Å¸â€Â¥ STEP 6 Ã¢â‚¬â€ DELETE EQUIPMENT LOG
    log_action(
        user=request.user,
        action='delete',
        instance=equipment,  # Note: equipment instance is deleted but variable still exists
        module='registration',
        changes={
            "equipment": equipment_name
        }
    )
    
    return redirect('manage_equipment')


# ================= STUDENT MANAGEMENT =================

@login_required
def register_student(request):
    if not has_permission(request.user, 'add'):
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)

        if form.is_valid():
            student = form.save()
            
            # Ã°Å¸â€Â¥ STEP 2 Ã¢â‚¬â€ REGISTER STUDENT LOG
            log_action(
                user=request.user,
                action='create',
                instance=student,
                module='registration',
                changes={
                    "student": f"{student.first_name} {student.last_name}",
                    "reg_no": student.registration_number
                }
            )

            messages.success(request, "Ã¢Å“â€¦ Student registered successfully!")
            return redirect('view_students')
        else:
            messages.error(request, "Ã¢ÂÅ’ Please fix the errors below.")
    else:
        form = StudentForm()

    return render(request, 'registration/user/register.html', {
        'form': form,
        'edit_mode': False
    })


@login_required
def edit_student(request, student_id):
    if not has_permission(request.user, 'edit'):
        return redirect('dashboard')
    
    student = get_object_or_404(Student, id=student_id)
    # Store old values to detect changes
    old_class = student.student_class
    old_status = student.school_status
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            updated_student = form.save()
            
            # Detect manual promotion or graduation
            class_changed = old_class != updated_student.student_class
            graduated_now = old_status != 'Graduated' and updated_student.school_status == 'Graduated'
            
            if class_changed or graduated_now:
                note = "Manual Class Update" if class_changed else "Manual Graduation"
                to_class = updated_student.student_class if updated_student.school_status != 'Graduated' else 'Graduated'
                
                StudentClassHistory.objects.create(
                    student=updated_student,
                    from_class=old_class,
                    to_class=to_class,
                    from_section=updated_student.section,
                    to_section=updated_student.section,
                    academic_year=str(timezone.now().year),
                    changed_by=request.user,
                    note=note
                )
            
            # Ã°Å¸â€Â¥ STEP 3 Ã¢â‚¬â€ EDIT STUDENT LOG
            log_action(
                user=request.user,
                action='update',
                instance=student,
                module='registration',
                changes={
                    "edited": True,
                    "student": student.registration_number
                }
            )
            
            messages.success(request, f"Ã¢Å“â€¦ Student {student.first_name} updated successfully!")
            return redirect('view_students')
        else:
            messages.error(request, "Ã¢ÂÅ’ Please fix the errors below.")
    else:
        form = StudentForm(instance=student)
    
    return render(request, 'registration/user/register.html', {
        'form': form,
        'edit_mode': True,
        'student': student
    })


@login_required
def view_students(request):
    if not has_permission(request.user, 'view'):
        return redirect('dashboard')

    students = Student.objects.filter(is_archived=False).exclude(school_status='Graduated')
    
    view_mode = request.GET.get('view_mode', 'class')
    selected_class = request.GET.get('selected_class', '')
    search_query = request.GET.get('search', '').strip()
    filter_field = request.GET.get('filter_field', '')
    filter_value = request.GET.get('filter_value', '').strip()
    
    if filter_field and filter_value:
        if filter_field in ['gender', 'health_status', 'school_status', 'student_class']:
            students = students.filter(**{filter_field: filter_value})
        elif filter_field in ['section']:
            students = students.filter(section=filter_value)
        else:
            students = students.filter(**{f'{filter_field}__icontains': filter_value})
    elif search_query:
        students = students.filter(
            Q(first_name__icontains=search_query) |
            Q(middle_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(registration_number__icontains=search_query) |
            Q(parent_name__icontains=search_query) |
            Q(parent_phone__icontains=search_query) |
            Q(tribe__icontains=search_query) |
            Q(region__icontains=search_query)
        )
    
    o_level_list = ['Form 1', 'Form 2', 'Form 3', 'Form 4']
    a_level_list = ['Form 5', 'Form 6']
    class_counts = {
        class_name: Student.objects.filter(
            is_archived=False,
            student_class=class_name
        ).exclude(school_status='Graduated').count()
        for class_name in o_level_list + a_level_list
    }
    
    o_level_classes = [c for c in o_level_list if class_counts.get(c, 0) > 0]
    a_level_classes = [c for c in a_level_list if class_counts.get(c, 0) > 0]
    
    if selected_class:
        students = students.filter(student_class=selected_class)
    
    students = students.order_by('student_class', 'section', 'first_name', 'last_name')
    paginator = Paginator(students, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    context = {
        'students': page_obj.object_list,
        'page_obj': page_obj,
        'class_counts': class_counts,
        'o_level_classes': o_level_classes,
        'a_level_classes': a_level_classes,
        'selected_class': selected_class,
        'view_mode': view_mode,
        'search_query': search_query,
        'filter_field': filter_field,
        'filter_value': filter_value,
        'has_filters': bool(search_query or filter_field),
        'total_students': Student.objects.filter(is_archived=False).exclude(school_status='Graduated').count(),
        'can_edit_students': has_permission(request.user, 'edit'),
        'can_delete_students': has_permission(request.user, 'delete'),
    }
    
    return render(request, 'registration/user/view_students.html', context)


@login_required
def archive_student(request, student_id):
    """Archive a student with timestamp"""
    if not has_permission(request.user, 'delete'):
        return redirect('dashboard')

    if request.method != 'POST':
        messages.error(request, "Archive must be confirmed from the student list.")
        return redirect('view_students')

    student = get_object_or_404(Student, id=student_id)
    
    # Use the helper method to archive with timestamp
    student.archive()
    
    # Ã°Å¸â€Â¥ STEP 4 Ã¢â‚¬â€ ARCHIVE STUDENT LOG
    log_action(
        user=request.user,
        action='update',
        instance=student,
        module='registration',
        changes={
            "archived": True
        }
    )
    
    messages.success(request, f"Ã°Å¸â€œÂ¦ Student {student.first_name} {student.last_name} archived successfully!")
    return redirect('view_students')


@login_required
def restore_student(request, student_id):
    """Restore an archived student"""
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    if request.method != 'POST':
        messages.error(request, "Restore must be confirmed from the archived list.")
        return redirect('archived_students')

    student = get_object_or_404(Student, id=student_id)
    
    # Use the helper method to restore and clear timestamp
    student.restore()
    
    
    # Ã°Å¸â€Â¥ STEP 5 Ã¢â‚¬â€ RESTORE STUDENT LOG
    log_action(
        user=request.user,
        action='update',
        instance=student,
        module='registration',
        changes={
            "restored": True
        }
    )
    
    messages.success(request, f"Ã¢Å“â€¦ Student {student.first_name} {student.last_name} restored successfully!")
    return redirect('view_students')

@login_required
def archived_students(request):
    """Display list of archived students ordered by archive date (most recent first)"""
    if not is_registration_admin(request.user):
        return redirect('dashboard')
    
    # Order by archived_at (most recent first) - this shows when they were archived
    archived_students_list = Student.objects.filter(is_archived=True).order_by('-archived_at')
    
    # Count total archived students
    archived_count = archived_students_list.count()
    
    return render(request, 'registration/admin/archived.html', {
        'students': archived_students_list,
        'archived_count': archived_count
    })

@login_required
def student_detail(request, student_id):
    if not has_permission(request.user, 'view'):
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id)

    return render(request, 'registration/user/student_detail.html', {
        'student': student,
        'can_edit_students': has_permission(request.user, 'edit'),
    })


# First, install reportlab if you haven't already:
# pip install reportlab

# Then replace your download_students_pdf and student_report_pdf functions with these:
@login_required
def download_students_pdf(request):
    if not has_permission(request.user, 'view'):
        return redirect('dashboard')
    
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    import os
    from django.conf import settings
    
    class_filter = request.GET.get('class', 'all')
    
    if class_filter == 'all':
        students = Student.objects.filter(is_archived=False).order_by('student_class', 'first_name')
        filename = f"All_Students_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
    else:
        students = Student.objects.filter(is_archived=False, student_class=class_filter).order_by('first_name')
        filename = f"{class_filter}_Students_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(A4),
                           rightMargin=0.8*cm, leftMargin=0.8*cm,
                           topMargin=1*cm, bottomMargin=0.8*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    logo_title_style = ParagraphStyle(
        'LogoTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,  # Center
        spaceAfter=0,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        alignment=1,
        spaceAfter=10
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.white,
        alignment=1,
        fontName='Helvetica-Bold'
    )
    
    # Get logo
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'school_logo.png')
    
    # Create centered header with logo above school name
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.5*cm, height=2.5*cm)
        
        # Centered logo table
        logo_table = Table([[logo]], colWidths=[20*cm])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(logo_table)
        elements.append(Spacer(1, 3))
    
    # School name centered
    elements.append(Paragraph("DODOMA SCHOOL", logo_title_style))
    elements.append(Spacer(1, 5))
    
    # Report title
    if class_filter == 'all':
        elements.append(Paragraph("ALL STUDENTS REPORT", logo_title_style))
    else:
        elements.append(Paragraph(f"{class_filter.upper()} STUDENTS REPORT", logo_title_style))
    
    elements.append(Spacer(1, 8))
    
    # Info line
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  Total Students: {students.count()}", subtitle_style))
    elements.append(Spacer(1, 10))
    
    # Table data - Essential columns only
    table_data = []
    
    headers = ['Reg No', 'Full Name', 'Class', 'Section', 'Gender', 'Parent Name', 'Parent Phone', 'Status']
    table_data.append(headers)
    
    for student in students:
        full_name = f"{student.first_name} {student.middle_name or ''} {student.last_name or ''}".strip()
        
        row = [
            student.registration_number or '',
            full_name,
            student.student_class or '',
            student.section or '',
            student.gender or '',
            student.parent_name or '',
            student.parent_phone or '',
            student.school_status or 'Active'
        ]
        table_data.append(row)
    
    # Column widths
    col_widths = [55, 75, 50, 40, 40, 80, 60, 45]
    
    pdf_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    pdf_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (4, 1), (4, -1), 'CENTER'),
        ('ALIGN', (7, 1), (7, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(pdf_table)
    elements.append(Spacer(1, 12))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#94a3b8'),
        alignment=1
    )
    elements.append(Paragraph("Dodoma School Management System - Official Student Report", footer_style))
    
    doc.build(elements)
    
    log_action(
        user=request.user,
        action='export',
        instance=None,
        module='registration',
        changes={
            'export_type': 'students_pdf',
            'class_filter': class_filter,
            'count': students.count()
        }
    )
    
    return response
@login_required
def student_report_pdf(request, student_id):
    if not has_permission(request.user, 'view'):
        return redirect('dashboard')
    
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    import os
    from django.conf import settings
    
    student = get_object_or_404(Student, id=student_id)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Student_{student.registration_number}_Report.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4,
                           rightMargin=1.5*cm, leftMargin=1.5*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,
        spaceAfter=5
    )
    
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#475569'),
        fontName='Helvetica-Bold'
    )
    
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#1e293b')
    )
    
    # Centered logo and header
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'school_logo.png')
    
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.5*cm, height=2.5*cm)
        logo_table = Table([[logo]], colWidths=[17*cm])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(logo_table)
        elements.append(Spacer(1, 5))
    
    elements.append(Paragraph("DODOMA SCHOOL", title_style))
    elements.append(Paragraph("STUDENT INFORMATION REPORT", title_style))
    elements.append(Spacer(1, 12))
    
    # Student Information Section
    elements.append(Paragraph("📋 STUDENT INFORMATION", section_style))
    
    personal_data = [
        ["Registration Number:", student.registration_number or 'N/A'],
        ["Full Name:", f"{student.first_name} {student.middle_name or ''} {student.last_name or ''}".strip()],
        ["Gender:", student.gender or 'N/A'],
        ["Date of Birth:", student.date_of_birth.strftime('%d/%m/%Y') if student.date_of_birth else 'N/A'],
        ["Class:", student.student_class or 'N/A'],
        ["Section:", student.section or 'N/A'],
        ["Admission Date:", student.date_of_admission.strftime('%d/%m/%Y') if student.date_of_admission else 'N/A'],
        ["Status:", student.school_status or 'Active'],
        ["Health Status:", student.health_status or 'Fit'],
    ]
    
    personal_table = Table(personal_data, colWidths=[4.5*cm, 11*cm])
    personal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elements.append(personal_table)
    elements.append(Spacer(1, 10))
    
    # Parent Information
    elements.append(Paragraph("📞 PARENT/GUARDIAN INFORMATION", section_style))
    
    parent_data = [
        ["Parent/Guardian:", student.parent_name or 'N/A'],
        ["Parent Phone:", student.parent_phone or 'N/A'],
        ["Alternate Phone:", student.parent_phone2 or 'N/A'],
        ["Emergency Contact:", student.nearby_person_phone or 'N/A'],
    ]
    
    parent_table = Table(parent_data, colWidths=[4.5*cm, 11*cm])
    parent_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elements.append(parent_table)
    elements.append(Spacer(1, 10))
    
    # Address Information
    elements.append(Paragraph("📍 ADDRESS INFORMATION", section_style))
    
    address_data = [
        ["Region:", student.region or 'N/A'],
        ["District:", student.district or 'N/A'],
        ["Ward:", student.ward or 'N/A'],
        ["Village:", student.village or 'N/A'],
    ]
    
    address_table = Table(address_data, colWidths=[4.5*cm, 11*cm])
    address_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    elements.append(address_table)
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#94a3b8'),
        alignment=1
    )
    elements.append(Spacer(1, 25))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
    elements.append(Paragraph("Dodoma School Management System", footer_style))
    
    doc.build(elements)
    
    log_action(
        user=request.user,
        action='export',
        instance=student,
        module='registration',
        changes={
            'export_type': 'student_single_pdf',
            'student_id': student.registration_number
        }
    )
    
    return response

# ================= IMPORT/EXPORT =================
@login_required
def import_students_excel(request):
    if not has_permission(request.user, 'add'):
        return redirect('dashboard')

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']

        if not excel_file.name.lower().endswith('.xlsx'):
            messages.error(request, "Please upload an .xlsx Excel file. Download the template if unsure.")
            return redirect('import_students')

        if excel_file.size > 10 * 1024 * 1024:
            messages.error(request, "File is too large. Maximum allowed size is 10MB.")
            return redirect('import_students')

        try:
            import openpyxl
            workbook = openpyxl.load_workbook(excel_file, data_only=True, read_only=True)
            sheet = workbook.active

            aliases = {
                'registration_number': ['registration number', 'registration no', 'reg no', 'reg number', 'admission number'],
                'first_name': ['first name', 'firstname', 'fname'],
                'middle_name': ['middle name', 'middlename', 'mname'],
                'last_name': ['last name', 'lastname', 'surname', 'lname'],
                'gender': ['gender', 'sex'],
                'date_of_birth': ['date of birth', 'dob', 'birth date'],
                'student_class': ['class', 'student class', 'form'],
                'section': ['section', 'stream', 'combination'],
                'date_of_admission': ['date of admission', 'admission date', 'joined date'],
                'region': ['region'],
                'district': ['district'],
                'division': ['division'],
                'ward': ['ward'],
                'village': ['village', 'street'],
                'tribe': ['tribe'],
                'last_school_attended': ['last school attended', 'previous school'],
                'parent_name': ['parent name', 'guardian name', 'parent', 'guardian'],
                'parent_phone': ['parent phone', 'phone', 'guardian phone', 'contact'],
                'parent_phone2': ['parent phone 2', 'second phone', 'alternate phone'],
                'nearby_person_phone': ['nearby person phone', 'emergency phone'],
                'health_status': ['health status', 'health'],
                'school_status': ['school status', 'status'],
            }

            headers = [normalize_header(cell.value) for cell in sheet[1]]
            column_position = {}
            for field, names in aliases.items():
                normalized_names = [normalize_header(name) for name in names]
                for index, header in enumerate(headers, start=1):
                    if header in normalized_names:
                        column_position[field] = index
                        break

            required_fields = [
                'registration_number', 'first_name', 'gender', 'date_of_birth',
                'student_class', 'section', 'date_of_admission', 'region',
                'district', 'ward', 'village', 'parent_name', 'parent_phone'
            ]
            missing = [field.replace('_', ' ').title() for field in required_fields if field not in column_position]
            if missing:
                messages.error(request, f"Missing required columns: {', '.join(missing)}")
                return redirect('import_students')

            existing_reg_numbers = set(Student.objects.values_list('registration_number', flat=True))
            seen_in_file = set()
            students_to_create = []
            errors = []
            duplicate_count = 0

            for row_num in range(2, sheet.max_row + 1):
                reg_value = get_cell(sheet, row_num, column_position, 'registration_number')
                if not reg_value:
                    continue

                registration_number = str(reg_value).strip()
                if not registration_number:
                    continue

                if registration_number in existing_reg_numbers or registration_number in seen_in_file:
                    duplicate_count += 1
                    errors.append(f"Row {row_num}: duplicate registration number {registration_number}.")
                    continue
                seen_in_file.add(registration_number)

                dob = parse_excel_date(get_cell(sheet, row_num, column_position, 'date_of_birth'))
                admission_date = parse_excel_date(get_cell(sheet, row_num, column_position, 'date_of_admission'))
                if not dob:
                    errors.append(f"Row {row_num}: invalid or missing date of birth.")
                    continue
                if not admission_date:
                    errors.append(f"Row {row_num}: invalid or missing date of admission.")
                    continue

                student = Student(
                    registration_number=registration_number,
                    first_name=str(get_cell(sheet, row_num, column_position, 'first_name') or '').strip(),
                    middle_name=str(get_cell(sheet, row_num, column_position, 'middle_name') or '').strip(),
                    last_name=str(get_cell(sheet, row_num, column_position, 'last_name') or '').strip(),
                    gender=normalize_gender(get_cell(sheet, row_num, column_position, 'gender')),
                    date_of_birth=dob,
                    student_class=normalize_class(get_cell(sheet, row_num, column_position, 'student_class')),
                    section=str(get_cell(sheet, row_num, column_position, 'section') or '').strip().upper(),
                    date_of_admission=admission_date,
                    region=str(get_cell(sheet, row_num, column_position, 'region') or '').strip(),
                    district=str(get_cell(sheet, row_num, column_position, 'district') or '').strip(),
                    division=str(get_cell(sheet, row_num, column_position, 'division') or '').strip(),
                    ward=str(get_cell(sheet, row_num, column_position, 'ward') or '').strip(),
                    village=str(get_cell(sheet, row_num, column_position, 'village') or '').strip(),
                    tribe=str(get_cell(sheet, row_num, column_position, 'tribe') or '').strip(),
                    last_school_attended=str(get_cell(sheet, row_num, column_position, 'last_school_attended') or '').strip(),
                    parent_name=str(get_cell(sheet, row_num, column_position, 'parent_name') or '').strip(),
                    parent_phone=str(get_cell(sheet, row_num, column_position, 'parent_phone') or '').strip(),
                    parent_phone2=str(get_cell(sheet, row_num, column_position, 'parent_phone2') or '').strip(),
                    nearby_person_phone=str(get_cell(sheet, row_num, column_position, 'nearby_person_phone') or '').strip(),
                    health_status=normalize_health(get_cell(sheet, row_num, column_position, 'health_status')),
                    school_status=normalize_status(get_cell(sheet, row_num, column_position, 'school_status')),
                )

                try:
                    student.full_clean()
                except ValidationError as exc:
                    errors.append(f"Row {row_num}: {'; '.join(exc.messages)}")
                    continue

                students_to_create.append(student)

            if students_to_create:
                with transaction.atomic():
                    Student.objects.bulk_create(students_to_create, batch_size=500)

                log_action(
                    user=request.user,
                    action='create',
                    instance=None,
                    module='registration',
                    changes={
                        "event": "bulk_import",
                        "success": len(students_to_create),
                        "failed": len(errors),
                        "duplicates": duplicate_count,
                    }
                )
                messages.success(request, f"Imported {len(students_to_create)} students successfully. {duplicate_count} duplicates skipped.")
            else:
                messages.error(request, "No students were imported. Please fix the file and try again.")

            for error in errors[:12]:
                messages.warning(request, error)
            if len(errors) > 12:
                messages.warning(request, f"{len(errors) - 12} more row issues were hidden.")

        except Exception as exc:
            messages.error(request, f"Error reading file: {exc}")

        return redirect('view_students')

    return render(request, 'registration/admin/import_students.html')


@login_required
def download_import_template(request):
    if not has_permission(request.user, 'add'):
        return redirect('dashboard')
    
    from openpyxl import Workbook
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Student Import Template"
    
    headers = [
        "Registration Number", "First Name", "Middle Name", "Last Name",
        "Gender", "Date of Birth", "Class", "Section", "Date of Admission",
        "Region", "District", "Division", "Ward", "Village", "Tribe",
        "Last School Attended", "Parent Name", "Parent Phone",
        "Parent Phone 2", "Nearby Person Phone", "Health Status", "School Status"
    ]
    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)

    example = [
        "REG2026001", "Asha", "Juma", "Mollel", "Female", "2012-03-14",
        "Form 1", "A", timezone.now().date().isoformat(), "Dodoma", "Dodoma",
        "", "Central", "Central", "", "", "Juma Mollel", "0712345678",
        "", "", "Fit", "Active"
    ]
    for col, value in enumerate(example, 1):
        ws.cell(row=2, column=col, value=value)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.xlsx"'
    wb.save(response)
    return response

# ================= ENTRY =================

@login_required
def registration_home(request):
    if request.user.is_superuser:
        return redirect('registration_admin_dashboard')

    if is_registration_admin(request.user):
        return redirect('registration_admin_dashboard')

    return redirect('view_students')

@login_required
def promote_students(request):
    """
    Handles the promotion of students to the next class or graduation.
    Allows selective promotion by class.
    """
    if not is_registration_admin(request.user):
        messages.error(request, "Access denied. Graduation records are for admins only.")
        return redirect('dashboard')

    promotion_map = {
        'Form 1': 'Form 2',
        'Form 2': 'Form 3',
        'Form 3': 'Form 4',
        'Form 5': 'Form 6',
    }
    graduating_classes = ['Form 4', 'Form 6']
    academic_year = request.POST.get('academic_year') or str(timezone.now().year)

    movable_classes = list(promotion_map.keys()) + graduating_classes
    processing_order = ['Form 6', 'Form 5', 'Form 4', 'Form 3', 'Form 2', 'Form 1']

    # Get counts for all classes to display in the form.
    counts = {
        class_name: Student.objects.filter(
            student_class=class_name,
            school_status='Active',
            is_archived=False
        ).count()
        for class_name in CLASS_ORDER
    }

    skipped_counts = {
        class_name: Student.objects.filter(
            student_class=class_name,
            is_archived=False
        ).exclude(school_status__in=['Active', 'Graduated']).count()
        for class_name in CLASS_ORDER
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        selected_classes = request.POST.getlist('classes_to_promote')
        selected_classes = [class_name for class_name in selected_classes if class_name in movable_classes]

        if action != 'confirm' or not selected_classes:
            messages.error(request, "Please select at least one class and confirm the promotion.")
            return redirect('promote_students')

        moved = 0
        graduated = 0
        skipped = 0

        with transaction.atomic():
            action_types = set()
            if any(class_name in promotion_map for class_name in selected_classes):
                action_types.add(PromotionBatch.ACTION_PROMOTION)
            if any(class_name in graduating_classes for class_name in selected_classes):
                action_types.add(PromotionBatch.ACTION_GRADUATION)

            batch = PromotionBatch.objects.create(
                academic_year=academic_year,
                action_type=PromotionBatch.ACTION_MIXED if len(action_types) > 1 else next(iter(action_types)),
                selected_classes=selected_classes,
                created_by=request.user,
            )

            selected_set = set(selected_classes)
            for from_class in processing_order:
                if from_class not in selected_set:
                    continue

                skipped += Student.objects.select_for_update().filter(
                    student_class=from_class,
                    is_archived=False
                ).exclude(school_status__in=['Active', 'Graduated']).count()

                if from_class in graduating_classes:
                    students_to_graduate = list(Student.objects.select_for_update().filter(
                        student_class=from_class, school_status='Active', is_archived=False
                    ))
                    for student in students_to_graduate:
                        StudentClassHistory.objects.create(
                            student=student, from_class=from_class, to_class='Graduated',
                            from_section=student.section, to_section=student.section,
                            academic_year=academic_year, changed_by=request.user, note='Graduation',
                            batch=batch
                        )
                        student.school_status = 'Graduated'
                        student.save(update_fields=['school_status'])
                        try:
                            from certificate.models import GraduateCollection
                            GraduateCollection.objects.get_or_create(student=student)
                        except Exception:
                            pass
                        graduated += 1

                elif from_class in promotion_map:
                    to_class = promotion_map[from_class]
                    students_to_promote = list(Student.objects.select_for_update().filter(
                        student_class=from_class, school_status='Active', is_archived=False
                    ))
                    for student in students_to_promote:
                        StudentClassHistory.objects.create(
                            student=student, from_class=from_class, to_class=to_class,
                            from_section=student.section, to_section=student.section,
                            academic_year=academic_year, changed_by=request.user, note='Annual class promotion',
                            batch=batch
                        )
                        student.student_class = to_class
                        student.save(update_fields=['student_class'])
                        moved += 1
                else:
                    messages.warning(request, f"Class '{from_class}' is not configured for promotion or graduation.")

            batch.promoted_count = moved
            batch.graduated_count = graduated
            batch.skipped_count = skipped
            batch.save(update_fields=['promoted_count', 'graduated_count', 'skipped_count'])

        log_action(
            user=request.user,
            action='update',
            instance=None,
            module='registration',
            changes={
                'event': 'selective_promotion',
                'academic_year': academic_year,
                'moved': moved,
                'graduated': graduated,
                'skipped': skipped,
                'selected_classes': selected_classes,
                'batch_id': str(batch.id),
            }
        )

        if skipped:
            messages.warning(request, f"{skipped} inactive or suspended students were left in their current class for review.")
        messages.success(request, f"Promotion complete: {moved} students promoted, {graduated} students graduated. Batch can be reverted if needed.")
        return redirect('view_students')

    return render(request, 'registration/admin/promote_students.html', {
        'counts': counts,
        'skipped_counts': skipped_counts,
        'promotion_map': promotion_map,
        'graduating_classes': graduating_classes,
        'academic_year': academic_year,
        'all_classes': CLASS_ORDER, # Pass all classes for checkboxes
    })


@login_required
def promotion_revert_list(request):
    """
    Displays recent promotion/graduation events so they can be undone.
    """
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    batches = PromotionBatch.objects.select_related('created_by', 'reverted_by').all()[:20]

    return render(request, 'registration/admin/promotion_revert_list.html', {
        'batches': batches
    })


@login_required
def undo_promotion_batch(request):
    """
    The 'Panic Button' to undo a promotion batch.
    """
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        
        if not batch_id:
            messages.error(request, "Invalid batch selected.")
            return redirect('promotion_revert_list')

        batch = get_object_or_404(PromotionBatch, id=batch_id)
        if batch.is_reverted:
            messages.warning(request, "This promotion batch has already been reverted.")
            return redirect('promotion_revert_list')

        history_records = batch.history_records.select_related('student').select_for_update()

        reverted_count = 0
        skipped_unsafe = 0
        
        with transaction.atomic():
            for history in history_records:
                student = history.student

                if history.to_class == 'Graduated':
                    can_revert = student.school_status == 'Graduated'
                else:
                    can_revert = (
                        student.student_class == history.to_class and
                        student.school_status == 'Active'
                    )

                if not can_revert:
                    skipped_unsafe += 1
                    continue

                student.student_class = history.from_class
                student.section = history.from_section or student.section
                
                if history.to_class == 'Graduated':
                    student.school_status = 'Active'
                
                student.save(update_fields=['student_class', 'section', 'school_status'])

                if history.to_class == 'Graduated':
                    collection = getattr(student, 'collection_record', None)
                    if collection and not any([
                        collection.necta_certificate_no,
                        collection.necta_result_slip_no,
                        collection.certificate_collected,
                        collection.result_slip_collected,
                        collection.notes,
                    ]):
                        collection.delete()

                reverted_count += 1
            
            batch.is_reverted = True
            batch.reverted_by = request.user
            batch.reverted_at = timezone.now()
            batch.save(update_fields=['is_reverted', 'reverted_by', 'reverted_at'])

        log_action(
            user=request.user,
            action='update',
            instance=None,
            module='registration',
            changes={
                "event": "promotion_reverted",
                "batch_id": str(batch.id),
                "students_affected": reverted_count,
                "skipped_unsafe": skipped_unsafe,
            }
        )

        if skipped_unsafe:
            messages.warning(request, f"{skipped_unsafe} records were not reverted because the student had changed after the batch.")
        messages.success(request, f"Successfully reverted {reverted_count} students to their previous state.")
        return redirect('view_students')

    return redirect('promotion_revert_list')
