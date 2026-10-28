import os
import django

# 1. Setup Django environment (Replace 'core' with your actual project folder name if different)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accreditation.models import Guest, Kid

# 2. Define 15 Sample Guests
sample_guests = [
    {
        "names": "James and Eleanor Vance",
        "spouse_name": "Eleanor Vance",
        "email": "j.vance@example.com", "phone": "555-0101",
        "nanny_name": "Sarah Jenkins", "nanny_count": 1,
        "ticket_number": "EVT-2024-A101",
        "kids": [{"name": "Leo", "age": 6, "gender": "Male"}, {"name": "Mia", "age": 4, "gender": "Female"}]
    },
    {
        "names": "Marcus Thorne",
        "spouse_name": "", "email": "m.thorne@example.com", "phone": "555-0102",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A102",
        "kids": []
    },
    {
        "names": "David and Chloe Kim",
        "spouse_name": "Chloe Kim",
        "email": "d.kim@example.com", "phone": "555-0103",
        "nanny_name": "Maria Garcia", "nanny_count": 1,
        "ticket_number": "EVT-2024-A103",
        "kids": [{"name": "Sophie", "age": 2, "gender": "Female"}]
    },
    {
        "names": "Olivia Martinez",
        "spouse_name": "", "email": "o.martinez@example.com", "phone": "555-0104",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A104",
        "kids": [{"name": "Noah", "age": 8, "gender": "Male"}]
    },
    {
        "names": "Robert and Linda Chen",
        "spouse_name": "Linda Chen",
        "email": "r.chen@example.com", "phone": "555-0105",
        "nanny_name": "David Okafor", "nanny_count": 1,
        "ticket_number": "EVT-2024-A105",
        "kids": [{"name": "Ethan", "age": 5, "gender": "Male"}, {"name": "Ava", "age": 7, "gender": "Female"}, {"name": "Lucas", "age": 3, "gender": "Male"}]
    },
    {
        "names": "William Hayes",
        "spouse_name": "", "email": "w.hayes@example.com", "phone": "555-0106",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A106",
        "kids": []
    },
    {
        "names": "Emma and Thomas Wright",
        "spouse_name": "Thomas Wright",
        "email": "e.wright@example.com", "phone": "555-0107",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A107",
        "kids": [{"name": "Oliver", "age": 1, "gender": "Male"}]
    },
    {
        "names": "Sophia Patel",
        "spouse_name": "", "email": "s.patel@example.com", "phone": "555-0108",
        "nanny_name": "Anita Desai", "nanny_count": 1,
        "ticket_number": "EVT-2024-A108",
        "kids": [{"name": "Aarav", "age": 4, "gender": "Male"}, {"name": "Veda", "age": 6, "gender": "Female"}]
    },
    {
        "names": "Alexander and Grace Ford",
        "spouse_name": "Grace Ford",
        "email": "a.ford@example.com", "phone": "555-0109",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A109",
        "kids": []
    },
    {
        "names": "Isabella Rossi",
        "spouse_name": "", "email": "i.rossi@example.com", "phone": "555-0110",
        "nanny_name": "Giulia Bianchi", "nanny_count": 1,
        "ticket_number": "EVT-2024-A110",
        "kids": [{"name": "Matteo", "age": 3, "gender": "Male"}]
    },
    {
        "names": "Daniel and Maya Johnson",
        "spouse_name": "Maya Johnson",
        "email": "d.johnson@example.com", "phone": "555-0111",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A111",
        "kids": [{"name": "Liam", "age": 9, "gender": "Male"}]
    },
    {
        "names": "Charlotte Davis",
        "spouse_name": "", "email": "c.davis@example.com", "phone": "555-0112",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A112",
        "kids": []
    },
    {
        "names": "Benjamin and Zoe Taylor",
        "spouse_name": "Zoe Taylor",
        "email": "b.taylor@example.com", "phone": "555-0113",
        "nanny_name": "Emma Wilson", "nanny_count": 1,
        "ticket_number": "EVT-2024-A113",
        "kids": [{"name": "Mason", "age": 5, "gender": "Male"}, {"name": "Ella", "age": 2, "gender": "Female"}]
    },
    {
        "names": "Lucas Anderson",
        "spouse_name": "", "email": "l.anderson@example.com", "phone": "555-0114",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A114",
        "kids": [{"name": "Harper", "age": 7, "gender": "Female"}]
    },
    {
        "names": "Amelia and Jack Wilson",
        "spouse_name": "Jack Wilson",
        "email": "a.wilson@example.com", "phone": "555-0115",
        "nanny_name": "", "nanny_count": 0,
        "ticket_number": "EVT-2024-A115",
        "kids": []
    }
]

# 3. Insert into Database
print("🚀 Populating 15 sample guests...")
for g_data in sample_guests:
    kids_data = g_data.pop("kids")
    
    guest, created = Guest.objects.get_or_create(
        ticket_number=g_data["ticket_number"], 
        defaults=g_data
    )
    
    if created:
        print(f"✅ Created: {guest.names} | Ticket: {guest.ticket_number}")
        for k_data in kids_data:
            Kid.objects.get_or_create(guest=guest, defaults=k_data)
    else:
        print(f"ℹ️  Already exists: {guest.names}")

print("\n🎉 Done! QR codes generated in 'media/qr_codes/'.")