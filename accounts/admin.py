from django.contrib import admin
from .models import User, Module, UserModule


admin.site.register(User)
admin.site.register(Module)
admin.site.register(UserModule)