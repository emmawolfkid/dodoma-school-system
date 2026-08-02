from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_approved = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return self.username
    
class Module(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
        self.name = self.name.lower()   # enforce lowercase
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class UserModule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)

    is_admin = models.BooleanField(default=False)

    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_view = models.BooleanField(default=True)
    is_exam_coordinator = models.BooleanField(default=False)

    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.module.name}"
