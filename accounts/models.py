from django.db import models
import secrets
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

# ---- Custom User Manager ----
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        
        return self.create_user(email, password, **extra_fields)
    
    
# ---- User Model ----
class User(AbstractBaseUser):
    ROLE_CHOICES = (
        ("user", "User"),
        ("admin", "Admin"),
    )
    
    email = models.EmailField(unique=True, db_index=True)
    password = models.CharField(max_length=128)
    name = models.CharField(max_length=100)
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    api_key = models.CharField(max_length=64, unique=True, db_index=True, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # # ---- Rate Limits ----
    # requests_per_hour = models.IntegerField(default=100)
    # requests_per_day = models.IntegerField(default=1000)
    # concurrent_jobs = models.IntegerField(default=3)
    
    # # ---- Usage Tracking ----
    # total_requests = models.IntegerField(default=0)
    # successful_requests = models.IntegerField(default=0)
    # failed_requests = models.IntegerField(default=0)
    # last_request_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(blank=True, null=True)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    
    objects = UserManager()

    def __str__(self):
        return self.email
    
    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser
    
    # ---- API Key Generator ----
    def generate_api_key(self):
        self.api_key = secrets.token_hex(32)  # 64-character hex string
        self.save(update_fields=["api_key"])
        return self.api_key
    