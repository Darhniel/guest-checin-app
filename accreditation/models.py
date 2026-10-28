import hashlib
import io
import os
import qrcode
import secrets
import string
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin') # Automatically make superusers 'admin'

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('ambassador', 'Brand Ambassador'),
    )
    username = None # We will use email as the username
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ambassador')
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    first_login = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = CustomUserManager()

    def __str__(self):
        return self.full_name or self.email

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='event_logos/', blank=True, null=True)
    location_text = models.CharField(max_length=255, blank=True, help_text="General location, e.g., 'Lagos, Nigeria'")
    start_date = models.DateField()
    end_date = models.DateField()
    daily_schedule = models.JSONField(default=dict, help_text='e.g., {"2026-11-15": {"start": "08:00", "end": "18:00"}}')
    custom_fields_schema = models.JSONField(default=dict, blank=True, help_text='Extra guest fields, e.g. {"fields": [{"key": "company", "label": "Company", "type": "text"}]}')
    enforce_hours = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_events')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Location(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.event.name})"

class GuestCategory(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6B7280', help_text="Hex color code")
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name

class UserEventAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_access')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='user_access')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='assignments_made')

    class Meta:
        unique_together = (('user', 'event'),)

    def __str__(self):
        return f"{self.user.full_name or self.user.email} -> {self.event.name}"

# ==========================================
# NEW PHASE 2 MODELS
# ==========================================

class Guest(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guests')
    category = models.ForeignKey(GuestCategory, on_delete=models.SET_NULL, null=True, blank=True)
    names = models.TextField()
    spouse_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    nanny_name = models.CharField(max_length=255, blank=True)
    nanny_count = models.IntegerField(default=0)
    allergies = models.TextField(blank=True)
    ticket_number = models.CharField(max_length=32, unique=True, blank=True, editable=False)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    custom_data = models.JSONField(default=dict, blank=True) # For Phase 5 custom fields
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.names

    def clean(self):
        """
        A guest is only usable if we can identify and contact them.

        Deliberately enforced here (and at the API/import boundary) rather than
        as a database CheckConstraint: rows created before this rule existed may
        already lack both email and phone, and a constraint would make the
        migration fail on that existing data.
        """
        errors = {}

        names = (self.names or '').strip()
        if not names:
            errors['names'] = 'At least one guest name is required.'

        if not (self.email or '').strip() and not (self.phone or '').strip():
            errors['email'] = 'Provide an email address or a phone number.'
            errors['phone'] = 'Provide a phone number or an email address.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        is_new = self.pk is None # Check if this is a brand new object

        # Auto-generate ticket number and QR code if not present
        # 1. Auto-generate ticket number if not present
        if not self.ticket_number:
            # Safeguard: Ensure the event is saved first so it has a real database ID
            if not self.event_id:
                self.event.save()
                
            # Generate base ticket number
            self.ticket_number = f"EVT-{self.event_id}-{secrets.token_hex(4).upper()}"
            
            # FIX 3: Loop to guarantee absolute uniqueness and prevent IntegrityErrors
            while Guest.objects.filter(ticket_number=self.ticket_number).exists():
                self.ticket_number = f"EVT-{self.event_id}-{secrets.token_hex(4).upper()}"
        
        # Save the object to the database first
        super().save(*args, **kwargs)
        
        # 2. Generate QR code only for newly created objects
        if is_new and not self.qr_code:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=1)
            qr.add_data(self.ticket_number)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            
            # Ensure directory exists
            qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
            os.makedirs(qr_dir, exist_ok=True)
            
            # FIX 4: Use Django's ContentFile. This is much safer than raw file paths 
            # because it works perfectly even if you later switch to cloud storage (like AWS S3).
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            filename = f"{self.ticket_number}.png"
            self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
            # Save the updated qr_code path to the database
            super().save(update_fields=['qr_code'])

    class Meta:
        indexes = [
            models.Index(fields=['event', 'ticket_number']),
            models.Index(fields=['event', 'names']),
            models.Index(fields=['email']),
        ]

class Kid(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='kids')
    name = models.CharField(max_length=255)
    age = models.IntegerField()
    gender = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.name} ({self.age})"

class Accreditation(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='accreditations')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='accreditations')
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='verifications')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    is_accredited = models.BooleanField(default=True)

    class Meta:
        # CRITICAL: Prevents double check-in for the same guest on the same date
        unique_together = (('guest', 'date'),)
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['event', 'date']),
            models.Index(fields=['verified_by', 'date']),
        ]

    def __str__(self):
        return f"{self.guest.names} - {self.date}"

def generate_api_key():
    return secrets.token_urlsafe(32)


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class OrganizerAPIKey(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='api_keys')
    organizer_name = models.CharField(max_length=255)
    # Only the SHA-256 digest of the key is ever stored; the raw value is
    # shown once at creation time and sent to the organizer by the admin.
    key_hash = models.CharField(max_length=64, unique=True)
    key_prefix = models.CharField(max_length=12)  # first bytes, for identification only
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='organizer_api_keys'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.organizer_name} - {self.event.name}"

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100) # e.g., "check_in", "api_guest_create"
    resource_type = models.CharField(max_length=50) # e.g., "Guest", "Accreditation"
    resource_id = models.IntegerField(null=True, blank=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.timestamp}"