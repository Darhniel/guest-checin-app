# Guest Accreditation Platform - User Guide

## For Admins

### Creating an Event

1. Log into the admin dashboard
2. Click "Events" → "Create Event"
3. Fill in event details:
   - Name, description, location
   - Start and end dates
   - Daily schedule (check-in hours per day)
4. Add accreditation locations (e.g., "Main Gate", "VIP Entrance")
5. Add guest categories (VVIP, VIP, Regular) with colors
6. (Optional) Define custom fields for additional guest info
7. Click "Create Event"

### Creating Ambassadors

1. Click "Ambassadors" → "Create Ambassador"
2. Enter full name, email, phone
3. Click "Generate" for a secure temporary password
4. Click "Create"
5. Copy the credentials and share securely with the ambassador
6. The ambassador will be forced to change their password on first login

### Assigning Ambassadors to Events

1. Go to "Events" → Click an event
2. Click the "Ambassadors" tab
3. Click "Assign Ambassadors"
4. Select one or more ambassadors
5. Click "Assign"

### Viewing Analytics

1. Go to "Events" → Click an event
2. Click the "Analytics" tab
3. See:
   - Total guests and check-in completion rate
   - Pie chart: breakdown by category
   - Bar chart: breakdown by location
   - Leaderboard: ambassador performance

---

## For Ambassadors

### First Login

1. Open the mobile app
2. Enter the email and temporary password provided by admin
3. You'll be prompted to change your password
4. Set a new secure password
5. You'll see the Home screen with your assigned events

### Checking In Guests

1. Tap an event from the Home screen
2. If the event has multiple locations, select your location
3. Choose how to check in:
   - **QR Scanner**: Tap "Open QR Scanner" and point at guest's QR code
   - **Manual Search**: Type the guest's name (minimum 3 characters)
4. If successful, you'll see "Access Granted" with guest details
5. If the guest is already checked in, you'll see "Access Denied"

### Offline Mode

- If you lose internet, you can still scan QR codes
- Scans are queued locally and sync automatically when connection returns
- You'll see a badge showing pending syncs
- If there's a conflict (guest already checked in by someone else), you'll be notified

---

## For Event Organizers (API Integration)

### Getting Your API Key

1. Contact the platform admin
2. They'll generate an API key for your event
3. Use this key in the `Authorization` header: `Bearer YOUR_API_KEY`

### Pushing Guest Lists

```bash
POST /api/organizers/events/{event_id}/guests/bulk/
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "guests": [
    {
      "adult_names": "John Doe",
      "email": "john@example.com",
      "phone": "555-1234",
      "category_name": "VIP",
      "custom_data": {
        "company": "Acme Corp",
        "dietary": "Vegetarian"
      },
      "kids": [
        {"name": "Timmy", "age": 5, "gender": "Male"}
      ]
    }
  ]
}
```
### Troubleshooting

## "Network request failed"
1. Check your internet connection
2. Verify the API URL is correct
3. Ensure the backend server is running

## "Already checked in"
1. The guest was already checked in by another ambassador
    - Check the activity log to see who and when
2. "Event has ended"
    - The event's end date has passed
    - Contact admin to extend the event if needed
3. "Check-ins not allowed at this time"
    - You're outside the event's daily check-in hours
    - Wait until the scheduled time or contact admin to adjust hours
