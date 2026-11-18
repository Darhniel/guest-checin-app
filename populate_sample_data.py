import os
import django

# 1. Setup Django environment (Replace 'core' with your actual project folder name if different)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accreditation.models import Guest

# 2. Define 15 Sample Guests
sample_guests = [
    {
        "first_name": "James", "last_name": "Vance",
        "email": "j.vance@example.com", "phone_number": "555-0101",
        "ticket_number": "EVT-2024-A101",
    },
    {
        "first_name": "Marcus", "last_name": "Thorne",
        "email": "m.thorne@example.com", "phone_number": "555-0102",
        "ticket_number": "EVT-2024-A102",
    },
    {
        "first_name": "David", "last_name": "Kim",
        "email": "d.kim@example.com", "phone_number": "555-0103",
        "ticket_number": "EVT-2024-A103",
    },
    {
        "first_name": "Olivia", "last_name": "Martinez",
        "email": "o.martinez@example.com", "phone_number": "555-0104",
        "ticket_number": "EVT-2024-A104",
    },
    {
        "first_name": "Robert", "last_name": "Chen",
        "email": "r.chen@example.com", "phone_number": "555-0105",
        "ticket_number": "EVT-2024-A105",
    },
    {
        "first_name": "William", "last_name": "Hayes",
        "email": "w.hayes@example.com", "phone_number": "555-0106",
        "ticket_number": "EVT-2024-A106",
    },
    {
        "first_name": "Emma", "last_name": "Wright",
        "email": "e.wright@example.com", "phone_number": "555-0107",
        "ticket_number": "EVT-2024-A107",
    },
    {
        "first_name": "Sophia", "last_name": "Patel",
        "email": "s.patel@example.com", "phone_number": "555-0108",
        "ticket_number": "EVT-2024-A108",
    },
    {
        "first_name": "Alexander", "last_name": "Ford",
        "email": "a.ford@example.com", "phone_number": "555-0109",
        "ticket_number": "EVT-2024-A109",
    },
    {
        "first_name": "Isabella", "last_name": "Rossi",
        "email": "i.rossi@example.com", "phone_number": "555-0110",
        "ticket_number": "EVT-2024-A110",
    },
    {
        "first_name": "Daniel", "last_name": "Johnson",
        "email": "d.johnson@example.com", "phone_number": "555-0111",
        "ticket_number": "EVT-2024-A111",
    },
    {
        "first_name": "Charlotte", "last_name": "Davis",
        "email": "c.davis@example.com", "phone_number": "555-0112",
        "ticket_number": "EVT-2024-A112",
    },
    {
        "first_name": "Benjamin", "last_name": "Taylor",
        "email": "b.taylor@example.com", "phone_number": "555-0113",
        "ticket_number": "EVT-2024-A113",
    },
    {
        "first_name": "Lucas", "last_name": "Anderson",
        "email": "l.anderson@example.com", "phone_number": "555-0114",
        "ticket_number": "EVT-2024-A114",
    },
    {
        "first_name": "Amelia", "last_name": "Wilson",
        "email": "a.wilson@example.com", "phone_number": "555-0115",
        "ticket_number": "EVT-2024-A115",
    },
]

# 3. Insert into Database
print("🚀 Populating 15 sample guests...")
for g_data in sample_guests:
    guest, created = Guest.objects.get_or_create(
        ticket_number=g_data["ticket_number"],
        defaults=g_data
    )

    if created:
        print(f"✅ Created: {guest.names} | Ticket: {guest.ticket_number}")
    else:
        print(f"ℹ️  Already exists: {guest.names}")

print("\n🎉 Done! QR codes generated in 'media/qr_codes/'.")
