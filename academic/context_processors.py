from .models import Notification, TeacherSubjectRequest
from accounts.models import UserModule

def academic_context(request):
    if request.user.is_authenticated:
        pending_requests = TeacherSubjectRequest.objects.filter(is_approved=False).count()
        notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-created_at')[:8]
        academic_modules = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True
        )
        return {
            'pending_requests': pending_requests,
            'notifications': notifications,
            'notification_count': notifications.count(),
            'academic_modules': academic_modules,
        }
    return {
        'pending_requests': 0,
        'notifications': [],
        'notification_count': 0,
        'academic_modules': [],
    }
