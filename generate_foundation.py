import os

BASE_DIR = r"c:\Users\iamro\Desktop\Adarsh-ID Panel"

FILES = {}

# We'll define all file contents here.

# ==========================================
# USERS DOMAIN (Phase 1 & 2)
# ==========================================
FILES['apps/users/models.py'] = """
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import RegexValidator
import uuid

class Role(models.TextChoices):
    PRO_USER = 'PRO_USER', 'Pro User'
    ADMIN = 'ADMIN', 'Admin'
    OPERATOR = 'OPERATOR', 'Operator'
    CLIENT = 'CLIENT', 'Client'
    ASSISTANT = 'ASSISTANT', 'Assistant'

class UserManager(BaseUserManager):
    def create_user(self, email=None, username=None, password=None, **extra_fields):
        if not email and not username:
            raise ValueError('Either email or username must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone = models.CharField(validators=[phone_regex], max_length=17, unique=True, null=True, blank=True)
    
    role = models.CharField(max_length=20, choices=Role.choices)
    
    # Organization relations
    organization = models.ForeignKey('organizations.Organization', on_delete=models.RESTRICT, null=True, blank=True, related_name='users')
    parent_client = models.ForeignKey('self', on_delete=models.RESTRICT, null=True, blank=True, related_name='assistants')
    
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    
    class Meta:
        db_table = 'users_user'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['phone']),
            models.Index(fields=['role']),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.is_active = False
        self.save()
"""

FILES['apps/users/urls.py'] = """
from django.urls import path

urlpatterns = [
    # API Routes will be here
]
"""

# ... I will write a more comprehensive generator ...
"""
