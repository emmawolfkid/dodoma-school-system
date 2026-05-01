from .models import TeacherSubjectRequest

def academic_context(request):
    if request.user.is_authenticated:
        pending_requests = TeacherSubjectRequest.objects.filter(is_approved=False).count()
        return {'pending_requests': pending_requests}
    return {'pending_requests': 0}