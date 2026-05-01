from django.contrib import admin
from .models import *

admin.site.register(Subject)
admin.site.register(Combination)
admin.site.register(Exam)
admin.site.register(StudentMark)
admin.site.register(Result)
admin.site.register(TeacherSubject)
admin.site.register(Notification)
from .models import Paper

@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('subject', 'paper_number', 'max_marks')
    list_filter = ('subject',)