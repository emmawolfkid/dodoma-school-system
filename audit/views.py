from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet

from accounts.models import UserModule
from .models import AuditLog


# 🔐 PERMISSION CHECK
def has_audit_access(user):
    if user.is_superuser:
        return True

    return UserModule.objects.filter(
        user=user,
        module__name='audit',
        is_approved=True
    ).exists()


# 📊 DASHBOARD
@login_required
def audit_dashboard(request):
    if not has_audit_access(request.user):
        return redirect('dashboard')

    logs = AuditLog.objects.all().order_by('-timestamp')[:10]

    context = {
        "total_logs": AuditLog.objects.count(),
        "recent_logs": logs,
        "is_admin": UserModule.objects.filter(
            user=request.user,
            module__name='audit',
            is_admin=True
        ).exists()
    }

    return render(request, "audit/dashboard.html", context)


# 📜 LOGS VIEW
@login_required
def audit_logs(request):
    if not has_audit_access(request.user):
        return redirect('dashboard')

    logs = AuditLog.objects.all().order_by('-timestamp')

    # 🔍 SEARCH
    search = request.GET.get('search', '')
    if search:
        logs = logs.filter(
            Q(user__username__icontains=search) |
            Q(module__icontains=search) |
            Q(action__icontains=search)
        )

    # 🎯 FILTERS
    module = request.GET.get('module')
    action = request.GET.get('action')
    date_filter = request.GET.get('date_filter')

    if module:
        logs = logs.filter(module=module)

    if action:
        logs = logs.filter(action=action)

    # 📅 DATE FILTERS
    now = timezone.now()

    if date_filter == "today":
        logs = logs.filter(timestamp__date=now.date())

    elif date_filter == "week":
        logs = logs.filter(timestamp__gte=now - timedelta(days=7))

    elif date_filter == "month":
        logs = logs.filter(timestamp__month=now.month)

    elif date_filter == "year":
        logs = logs.filter(timestamp__year=now.year)

    # 🔐 SECURITY (non-admin sees own logs only)
    is_admin = request.user.is_superuser or UserModule.objects.filter(
       user=request.user,
       module__name='audit',
       is_admin=True
    ).exists()

    if not is_admin:
        logs = logs.filter(user=request.user)

    # 📄 PAGINATION
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    logs = paginator.get_page(page_number)

    return render(request, "audit/logs.html", {
        "logs": logs,
        "search": search,
        "date_filter": date_filter,
    })


# 📄 PDF EXPORT with Logo and Professional Styling
@login_required
def export_audit_pdf(request):
    if not has_audit_access(request.user):
        return redirect('dashboard')
    
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    from django.conf import settings
    from io import BytesIO
    
    logs = AuditLog.objects.all().order_by('-timestamp')
    
    # 📅 SAME FILTERS
    date_filter = request.GET.get('date_filter')
    action_filter = request.GET.get('action', '')
    search_query = request.GET.get('search', '')
    now = timezone.now()
    
    if date_filter == "today":
        logs = logs.filter(timestamp__date=now.date())
        title = "Today's Audit Logs"
        date_range = f"Generated for: {now.strftime('%B %d, %Y')}"
    elif date_filter == "week":
        logs = logs.filter(timestamp__gte=now - timedelta(days=7))
        title = "Weekly Audit Logs"
        date_range = f"Last 7 Days - {now.strftime('%B %d, %Y')}"
    elif date_filter == "month":
        logs = logs.filter(timestamp__month=now.month)
        title = "Monthly Audit Logs"
        date_range = f"Month of {now.strftime('%B %Y')}"
    elif date_filter == "year":
        logs = logs.filter(timestamp__year=now.year)
        title = "Yearly Audit Logs"
        date_range = f"Year {now.strftime('%Y')}"
    else:
        title = "Complete Audit Logs"
        date_range = f"All Time - Generated {now.strftime('%B %d, %Y')}"
    
    # Apply action filter if present
    if action_filter:
        logs = logs.filter(action=action_filter)
        title += f" - {action_filter.upper()} Actions"
    
    # Apply search filter if present
    if search_query:
        logs = logs.filter(
            Q(user__username__icontains=search_query) |
            Q(module__icontains=search_query) |
            Q(action__icontains=search_query)
        )
        title += f" (Search: {search_query})"
    
    # 🔐 SECURITY
    is_admin = request.user.is_superuser or UserModule.objects.filter(
        user=request.user,
        module__name='audit',
        is_admin=True
    ).exists()
    
    if not is_admin:
        logs = logs.filter(user=request.user)
    
    # 📄 PDF Response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="audit_logs_{now.strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=landscape(A4),
                           rightMargin=1*cm, leftMargin=1*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)
    
    elements = []
    
    # Custom styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,  # Center
        spaceAfter=5
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=9,
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
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#94a3b8'),
        alignment=1,
        spaceAfter=5
    )
    
    # Get logo path
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'school_logo.png')
    
    # Try alternative logo paths if main doesn't exist
    if not os.path.exists(logo_path):
        logo_path = os.path.join(settings.STATIC_ROOT, 'images', 'school_logo.png')
    if not os.path.exists(logo_path):
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    
    # Create header with logo and school name
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.2*cm, height=2.2*cm)
        
        # Logo table centered
        logo_table = Table([[logo]], colWidths=[26*cm])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(logo_table)
        elements.append(Spacer(1, 5))
    
    # School name
    elements.append(Paragraph("DODOMA SECONDARY SCHOOL", title_style))
    elements.append(Paragraph("AUDIT TRAIL REPORT", title_style))
    elements.append(Spacer(1, 5))
    
    # Report info
    elements.append(Paragraph(title, subtitle_style))
    elements.append(Paragraph(date_range, subtitle_style))
    elements.append(Paragraph(f"Generated by: {request.user.username} | Total Records: {logs.count()}", subtitle_style))
    elements.append(Spacer(1, 10))
    
    # Prepare table data
    data = [['User', 'Action', 'Model', 'Module', 'Timestamp']]
    
    for log in logs[:1000]:  # Limit to 1000 records for PDF performance
        # Format action with badge-like text
        action_display = log.action.upper() if log.action else '-'
        
        # Format timestamp
        timestamp_str = log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else '-'
        
        data.append([
            str(log.user or 'System'),
            action_display,
            str(log.model_name or '-'),
            str(log.module or '-'),
            timestamp_str
        ])
    
    # Calculate column widths
    col_widths = [5*cm, 3.5*cm, 5*cm, 4*cm, 5.5*cm]
    
    # Create table
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Style the table
    table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Body style
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Action column center
        ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Timestamp center
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # Add special colors for action types
    for i, row in enumerate(data[1:], start=1):
        action = row[1] if len(row) > 1 else ''
        if 'CREATE' in action:
            table.setStyle(TableStyle([('TEXTCOLOR', (1, i), (1, i), colors.HexColor('#166534'))]))
        elif 'UPDATE' in action:
            table.setStyle(TableStyle([('TEXTCOLOR', (1, i), (1, i), colors.HexColor('#9a3412'))]))
        elif 'DELETE' in action:
            table.setStyle(TableStyle([('TEXTCOLOR', (1, i), (1, i), colors.HexColor('#991b1b'))]))
    
    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # Footer with copyright
    footer_text = f"""
    <b>Dodoma Secondary School</b> | P.O. Box 123, Dodoma, Tanzania<br/>
    Tel: +255 xxx xxx xxx | Email: info@dodomasec.ac.tz<br/>
    <font color="#666666">© 2026 Dodoma Secondary School. All Rights Reserved.</font><br/>
    <font color="#999999" size="8">This is a system-generated audit trail report. For inquiries, contact the system administrator.</font>
    """
    
    elements.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(elements)
    
    return response