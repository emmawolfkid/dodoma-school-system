from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from datetime import datetime
import io

from accounts.models import UserModule, Module
from .models import Student, Equipment
from .forms import StudentForm
from audit.models import AuditLog


# 🔥 CENTRAL PERMISSION SYSTEM (VERY IMPORTANT)
def has_permission(user, perm):
    if user.is_superuser:
        return True

    if UserModule.objects.filter(
        user=user,
        module__name='registration',
        is_admin=True,
        is_approved=True
    ).exists():
        return True

    return UserModule.objects.filter(
        user=user,
        module__name='registration',
        is_approved=True,
        **{f'can_{perm}': True}
    ).exists()


def is_registration_admin(user):
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
    user.password = make_password("123456")
    user.save()
    messages.success(request, f"Password reset for {user.username}")

    return redirect('manage_registration_users')


@login_required
def manage_equipment(request):
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Equipment.objects.create(name=name)

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
    
    return redirect('manage_equipment')


@login_required
def delete_equipment(request, equipment_id):
    if not is_registration_admin(request.user):
        return redirect('dashboard')
    
    equipment = get_object_or_404(Equipment, id=equipment_id)
    equipment.delete()
    
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

            AuditLog.objects.create(
                user=request.user,
                action="CREATE_STUDENT",
                module="registration",
                description=f"Registered {student.first_name}"
            )

            messages.success(request, "✅ Student registered successfully!")
            return redirect('view_students')
        else:
            messages.error(request, "❌ Please fix the errors below.")
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
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Student {student.first_name} updated successfully!")
            return redirect('view_students')
        else:
            messages.error(request, "❌ Please fix the errors below.")
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

    students = Student.objects.filter(is_archived=False)
    
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
    
    class_counts = {}
    o_level_list = ['Form 1', 'Form 2', 'Form 3', 'Form 4']
    a_level_list = ['Form 5', 'Form 6']
    
    for class_name in o_level_list + a_level_list:
        count = Student.objects.filter(is_archived=False, student_class=class_name).count()
        if count > 0:
            class_counts[class_name] = count
    
    o_level_classes = [c for c in o_level_list if c in class_counts]
    a_level_classes = [c for c in a_level_list if c in class_counts]
    
    students_by_class = {}
    all_students_list = []
    
    if view_mode == 'all':
        all_students_list = students.order_by('first_name')
    else:
        if selected_class:
            students = students.filter(student_class=selected_class)
            students_by_class[selected_class] = students.order_by('first_name')
        else:
            for class_name in o_level_classes + a_level_classes:
                class_students = students.filter(student_class=class_name).order_by('first_name')
                if class_students.exists():
                    students_by_class[class_name] = class_students
    
    context = {
        'students': students,
        'students_by_class': students_by_class,
        'all_students': all_students_list,
        'class_counts': class_counts,
        'o_level_classes': o_level_classes,
        'a_level_classes': a_level_classes,
        'selected_class': selected_class,
        'view_mode': view_mode,
        'search_query': search_query,
        'filter_field': filter_field,
        'filter_value': filter_value,
        'has_filters': bool(search_query or filter_field),
        'total_students': Student.objects.filter(is_archived=False).count(),
    }
    
    return render(request, 'registration/user/view_students.html', context)


@login_required
def archive_student(request, student_id):
    """Archive a student with timestamp"""
    if not has_permission(request.user, 'delete'):
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id)
    
    # Use the helper method to archive with timestamp
    student.archive()
    
    # Log the action for audit trail
    AuditLog.objects.create(
        user=request.user,
        action="ARCHIVE_STUDENT",
        module="registration",
        description=f"Archived student: {student.first_name} {student.last_name} (Reg: {student.registration_number})"
    )
    
    messages.success(request, f"📦 Student {student.first_name} {student.last_name} archived successfully!")
    return redirect('view_students')


@login_required
def restore_student(request, student_id):
    """Restore an archived student"""
    if not is_registration_admin(request.user):
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id)
    
    # Use the helper method to restore and clear timestamp
    student.restore()
    
    # Log the action for audit trail
    AuditLog.objects.create(
        user=request.user,
        action="RESTORE_STUDENT",
        module="registration",
        description=f"Restored student: {student.first_name} {student.last_name} (Reg: {student.registration_number})"
    )
    
    messages.success(request, f"✅ Student {student.first_name} {student.last_name} restored successfully!")
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
        'student': student
    })


@login_required
def download_students_pdf(request):
    if not has_permission(request.user, 'view'):
        return redirect('dashboard')
    
    class_filter = request.GET.get('class', 'all')
    
    if class_filter == 'all':
        students = Student.objects.filter(is_archived=False).order_by('student_class', 'first_name')
        filename = "All_Students_Report"
    else:
        students = Student.objects.filter(is_archived=False, student_class=class_filter).order_by('first_name')
        filename = f"{class_filter}_Students_Report"
    
    # Create HTML content that users can print to PDF
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Student Report</title>
        <style>
            @page {{ size: A4 landscape; margin: 1cm; }}
            @media print {{
                body {{ margin: 0; padding: 20px; }}
                .no-print {{ display: none; }}
            }}
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            h1 {{ color: #4f46e5; text-align: center; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }}
            .info {{ text-align: center; margin: 20px 0; color: #666; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background: #4f46e5; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #999; }}
            .print-btn {{ text-align: center; margin-bottom: 20px; }}
            .print-btn button {{ background: #4f46e5; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="print-btn no-print">
            <button onclick="window.print()">🖨️ Print / Save as PDF</button>
        </div>
        
        <h1>📚 Dodoma School Management System</h1>
        <div class="info">
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Total Students:</strong> {students.count()}</p>
        </div>
        
        <table>
            <thead>
                <tr><th>Reg No</th><th>Full Name</th><th>Class</th><th>Section</th><th>Parent Phone</th><th>Status</th></tr>
            </thead>
            <tbody>
    '''
    
    for student in students:
        full_name = f"{student.first_name} {student.middle_name or ''} {student.last_name or ''}".strip()
        html_content += f'<tr><td>{student.registration_number}</td><td>{full_name}</td><td>{student.student_class}</td><td>{student.section}</td><td>{student.parent_phone}</td><td>{student.school_status}</td></tr>'
    
    html_content += f'''
            </tbody>
        </table>
        <div class="footer">
            <p>Dodoma School Management System</p>
        </div>
    </body>
    </html>
    '''
    
    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="{filename}.html"'
    return response


@login_required
def student_report_pdf(request, student_id):
    if not has_permission(request.user, 'view'):
        return redirect('dashboard')
    
    student = get_object_or_404(Student, id=student_id)
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Student Report - {student.first_name}</title>
        <style>
            @page {{ size: A4; margin: 1cm; }}
            @media print {{ .no-print {{ display: none; }} }}
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            .header {{ text-align: center; border-bottom: 2px solid #4f46e5; padding-bottom: 20px; margin-bottom: 30px; }}
            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            .info-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; }}
            .label {{ font-weight: bold; color: #4f46e5; }}
            .print-btn {{ text-align: center; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="print-btn no-print">
            <button onclick="window.print()">🖨️ Print / Save as PDF</button>
        </div>
        <div class="header">
            <h1>Student Information Report</h1>
            <p>Dodoma School Management System</p>
        </div>
        <div class="info-grid">
            <div class="info-box">
                <p><span class="label">Full Name:</span> {student.first_name} {student.middle_name or ''} {student.last_name or ''}</p>
                <p><span class="label">Registration Number:</span> {student.registration_number}</p>
                <p><span class="label">Class:</span> {student.student_class}</p>
                <p><span class="label">Section:</span> {student.section}</p>
            </div>
            <div class="info-box">
                <p><span class="label">Parent/Guardian:</span> {student.parent_name or 'Not specified'}</p>
                <p><span class="label">Parent Phone:</span> {student.parent_phone or 'Not specified'}</p>
                <p><span class="label">Health Status:</span> {student.health_status or 'Fit'}</p>
                <p><span class="label">School Status:</span> {student.school_status}</p>
            </div>
        </div>
        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    '''
    
    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="Student_{student.registration_number}_Report.html"'
    return response


# ================= IMPORT/EXPORT =================
@login_required
def import_students_excel(request):
    if not has_permission(request.user, 'add'):
        return redirect('dashboard')
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Please upload an Excel file (.xlsx or .xls)")
            return redirect('import_students')
        
        try:
            import openpyxl
            from openpyxl.utils import get_column_letter
            from datetime import datetime, timedelta
            
            # Load workbook with data_only=True to get calculated values
            workbook = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = workbook.active
            
            # Print debug info
            print(f"Sheet name: {sheet.title}")
            print(f"Max row: {sheet.max_row}, Max col: {sheet.max_column}")
            
            # Read headers from first row
            headers = []
            for col in range(1, sheet.max_column + 1):
                cell_value = sheet.cell(row=1, column=col).value
                if cell_value:
                    headers.append(str(cell_value).strip().lower())
                else:
                    headers.append('')
            
            print(f"Headers found: {headers}")
            
            # Define column mapping
            column_mapping = {
                'registration_number': ['registration_number', 'registration no', 'reg no', 'registration number'],
                'first_name': ['first_name', 'first name', 'firstname', 'fname'],
                'middle_name': ['middle_name', 'middle name', 'middlename', 'mname'],
                'last_name': ['last_name', 'last name', 'lastname', 'lname'],
                'gender': ['gender', 'sex'],
                'date_of_birth': ['date_of_birth', 'date of birth', 'dob', 'birth date', 'birthdate'],
                'student_class': ['class', 'student_class', 'form'],
                'section': ['section', 'sec', 'stream'],
                'parent_name': ['parent_name', 'parent name', 'parent', 'guardian'],
                'parent_phone': ['parent_phone', 'parent phone', 'phone', 'contact'],
            }
            
            # Map columns
            column_position = {}
            for model_field, possible_names in column_mapping.items():
                for idx, header in enumerate(headers):
                    if header and header.lower() in [n.lower() for n in possible_names]:
                        column_position[model_field] = idx + 1
                        print(f"Mapped {model_field} to column {idx + 1} (header: {header})")
                        break
            
            # Check required columns
            required_fields = ['registration_number', 'first_name', 'student_class', 'section', 'gender', 'date_of_birth', 'parent_name', 'parent_phone']
            missing_required = [f for f in required_fields if f not in column_position]
            if missing_required:
                messages.error(request, f"Missing required columns: {', '.join(missing_required)}. Please check your Excel headers.")
                return redirect('import_students')
            
            # Process rows
            success_count = 0
            error_count = 0
            duplicate_count = 0
            errors = []
            success_details = []
            
            for row_num in range(2, min(sheet.max_row + 1, 100)):  # Limit to first 100 rows for testing
                try:
                    # Get registration number
                    reg_col = column_position['registration_number']
                    reg_value = sheet.cell(row=row_num, column=reg_col).value
                    
                    if not reg_value:
                        errors.append(f"Row {row_num}: No registration number found")
                        error_count += 1
                        continue
                    
                    registration_number = str(reg_value).strip()
                    
                    # Check duplicate
                    if Student.objects.filter(registration_number=registration_number).exists():
                        duplicate_count += 1
                        errors.append(f"Row {row_num}: Duplicate registration number '{registration_number}'")
                        continue
                    
                    # Get first name
                    first_col = column_position['first_name']
                    first_value = sheet.cell(row=row_num, column=first_col).value
                    if not first_value:
                        errors.append(f"Row {row_num}: Missing first name")
                        error_count += 1
                        continue
                    first_name = str(first_value).strip()
                    
                    # Get class
                    class_col = column_position['student_class']
                    class_value = sheet.cell(row=row_num, column=class_col).value
                    student_class = str(class_value).strip() if class_value else 'Form 1'
                    # Normalize class
                    class_map = {
                        'form1': 'Form 1', 'form 1': 'Form 1', 'Form 1': 'Form 1',
                        'form2': 'Form 2', 'form 2': 'Form 2', 'Form 2': 'Form 2',
                        'form3': 'Form 3', 'form 3': 'Form 3', 'Form 3': 'Form 3',
                        'form4': 'Form 4', 'form 4': 'Form 4', 'Form 4': 'Form 4',
                        'form5': 'Form 5', 'form 5': 'Form 5', 'Form 5': 'Form 5',
                        'form6': 'Form 6', 'form 6': 'Form 6', 'Form 6': 'Form 6',
                    }
                    student_class = class_map.get(student_class.lower(), student_class)
                    
                    # Get section
                    section_col = column_position['section']
                    section_value = sheet.cell(row=row_num, column=section_col).value
                    section = str(section_value).strip().upper() if section_value else 'A'
                    
                    # Get gender
                    gender_col = column_position['gender']
                    gender_value = sheet.cell(row=row_num, column=gender_col).value
                    gender = 'Male' if gender_value and str(gender_value).upper() in ['MALE', 'M'] else 'Female'
                    
                    # Get date of birth
                    dob_col = column_position['date_of_birth']
                    dob_value = sheet.cell(row=row_num, column=dob_col).value
                    date_of_birth = None
                    if dob_value and str(dob_value) != '#VALUE!':
                        try:
                            if isinstance(dob_value, (int, float)):
                                # Excel date
                                date_of_birth = datetime(1899, 12, 30) + timedelta(days=dob_value)
                                date_of_birth = date_of_birth.date()
                            elif isinstance(dob_value, datetime):
                                date_of_birth = dob_value.date()
                            elif isinstance(dob_value, str):
                                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                                    try:
                                        date_of_birth = datetime.strptime(dob_value, fmt).date()
                                        break
                                    except ValueError:
                                        continue
                        except Exception as e:
                            errors.append(f"Row {row_num}: Invalid date format for DOB: {dob_value}")
                    
                    if not date_of_birth:
                        date_of_birth = datetime.now().date()
                    
                    # Get parent name
                    parent_col = column_position['parent_name']
                    parent_value = sheet.cell(row=row_num, column=parent_col).value
                    parent_name = str(parent_value).strip() if parent_value else 'Not Provided'
                    
                    # Get parent phone
                    phone_col = column_position['parent_phone']
                    phone_value = sheet.cell(row=row_num, column=phone_col).value
                    parent_phone = str(phone_value).strip() if phone_value else '0712345678'
                    
                    # Get middle and last name
                    middle_name = ''
                    last_name = ''
                    if 'middle_name' in column_position:
                        mid_col = column_position['middle_name']
                        mid_value = sheet.cell(row=row_num, column=mid_col).value
                        if mid_value:
                            middle_name = str(mid_value).strip()
                    
                    if 'last_name' in column_position:
                        last_col = column_position['last_name']
                        last_value = sheet.cell(row=row_num, column=last_col).value
                        if last_value:
                            last_name = str(last_value).strip()
                    
                    # Create student
                    student = Student(
                        registration_number=registration_number,
                        first_name=first_name,
                        middle_name=middle_name,
                        last_name=last_name,
                        gender=gender,
                        date_of_birth=date_of_birth,
                        student_class=student_class,
                        section=section,
                        date_of_admission=datetime.now().date(),
                        region='Dodoma',
                        district='Dodoma',
                        division='',
                        ward='Central',
                        village='Central',
                        tribe='',
                        last_school_attended='',
                        parent_name=parent_name,
                        parent_phone=parent_phone,
                        parent_phone2='',
                        nearby_person_phone='',
                        health_status='Fit',
                        school_status='Active',
                    )
                    
                    student.save()
                    success_count += 1
                    success_details.append(f"✓ {registration_number} - {first_name}")
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {row_num}: {str(e)}")
            
            # Show detailed results
            if success_count > 0:
                messages.success(request, f"✅ Import complete! Success: {success_count}, Failed: {error_count}, Duplicates: {duplicate_count}")
                
                # Show first 5 successful imports
                if success_details:
                    messages.info(request, f"Successfully imported: {', '.join(success_details[:5])}")
                    if len(success_details) > 5:
                        messages.info(request, f"... and {len(success_details) - 5} more")
            else:
                messages.error(request, f"❌ Import failed! No students were imported. Success: {success_count}, Failed: {error_count}, Duplicates: {duplicate_count}")
            
            # Show errors
            if errors:
                for error in errors[:10]:
                    messages.warning(request, error)
                if len(errors) > 10:
                    messages.warning(request, f"... and {len(errors) - 10} more errors")
                    
        except Exception as e:
            messages.error(request, f"Error reading file: {str(e)}")
            import traceback
            traceback.print_exc()
        
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
    
    headers = ["Registration Number", "First Name", "Middle Name", "Last Name", "Gender", "Date of Birth", "Class", "Section", "Parent Name", "Parent Phone"]
    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)
    
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

