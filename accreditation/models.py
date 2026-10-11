import os
import qrcode
from django.db import models
from django.conf import settings

class Guest(models.Model):
    adult_names = models.TextField()
    spouse_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    nanny_name = models.CharField(max_length=255, blank=True)
    nanny_count = models.IntegerField(default=0)
    allergies = models.TextField(blank=True)
    ticket_number = models.CharField(max_length=16, unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    qrcode_sent = models.BooleanField(default=False)  # For QR code sent
    reject_sent = models.BooleanField(default=False)  # For reject email sent
    is_sent = models.BooleanField(default=False)  # For confirmation sent
    message_sid = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.adult_names

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import secrets
            import string
            self.ticket_number = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        if not self.qr_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )
            qr.add_data(self.ticket_number)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            qr_path = os.path.join(settings.MEDIA_ROOT, 'qr_codes', f'{self.ticket_number}.png')
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            img.save(qr_path)
            self.qr_code = f'qr_codes/{self.ticket_number}.png'
        super().save(*args, **kwargs)

class Kid(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='kids')
    name = models.CharField(max_length=255)
    age = models.IntegerField()
    gender = models.CharField(max_length=50, blank=True)

class Accreditation(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='accreditations', null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True, editable=False)
    is_accredited = models.BooleanField(default=True)
    time = models.TimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ['-date', '-time']

# class Accreditation(models.Model):
#     guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='accreditations', null=True, blank=True)
#     date = models.DateTimeField(auto_now_add=True, editable=False, blank=False)
#     is_accredited = models.BooleanField(default=False)
#     time = models.TimeField(auto_now_add=True, editable=False, blank=False)

#     def __str__(self):
#         if self.guest:
#             return f"{self.guest.adult_names} - {self.date} {self.time}"
#         return f"Accreditation - {self.date} {self.time}"

#     class Meta:
#         unique_together = (('guest', 'date'))
#         ordering = ['-date', '-time']
