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

### Unassigning Ambassadors from Events

1. Go to "Events" → Click an event
2. Click the "Ambassadors" tab
3. Click the unassign (minus) icon next to the ambassador you want to remove
4. The ambassador is removed immediately and can be re-assigned later from "Assign Ambassadors"

### Editing an Event

1. Go to "Events" → Click an event
2. Click "Edit event"
3. Update the details, accreditation points, guest categories, daily hours, or custom fields
4. Click "Save changes"
5. Removed accreditation points and categories are hidden for new check-ins while historical records are kept

### Deleting an Ambassador

1. Go to "Ambassadors"
2. Click the actions menu next to the ambassador and choose "Delete ambassador"
3. Confirm the deletion
4. The ambassador loses access to all events immediately. Past check-ins remain in reports, but are no longer attributed to them

### Viewing an Event's Guest Register

1. Open the event and switch to the **Guests** tab
2. Search or filter by check-in status to find any guest
3. Each row shows the ticket number, category, and check-in history
4. "Open full report" jumps to the printable report and Excel export

### Arrivals Feed

The event's **Analytics** tab shows an "Arrivals today" feed — every
accreditation recorded today, newest first, with category, location, and
the ambassador who verified the guest.

### Changing Your Password

Use the account menu (avatar) → **Change password**. Enter your current
password, then the new one twice. The change applies immediately; other
signed-in devices keep working until their token expires.

### Deleting an Event

1. Open the event → **Edit event** → **Delete event**
2. Confirm in the dialog — this permanently removes the event, its
   guests, categories, accreditation points, and organizer API keys
3. You are returned to the events list

### Editing an Ambassador

On the **Team** page, open the ⋯ menu on an ambassador's row and choose
**Edit details** to fix their name or phone number. The email is the
sign-in identity and cannot be changed.

### Managing Organizer API KeysLet an event organizer push their guest list directly into your event from
their own system.

1. Open the event and switch to the **Organizer** tab
2. Copy the **endpoint** shown there — this is what the organizer calls
3. Click **Generate key**, enter the organizer's name, and submit
4. The full key is shown **once** — copy both the key and the endpoint and
   send them to the organizer over a secure channel (never a public thread)
5. Every key is scoped to a single event's guest-ingest endpoint; nothing else

Security notes:

- The backend stores only a SHA-256 hash of each key; the raw value is never
  retrievable after creation
- Requests guess-proof: per-IP rate limiting on the ingest endpoint, and a
  revoked key stops working immediately
- If a key leaks, revoke it in the **API keys** list and issue a new one
- The list shows masked keys (`prefix + ••••`) with created/last-used times

Ingest limits: up to 1000 guests per request; duplicate guests (same email,
or same name when no email is given) are skipped rather than re-created.

### Viewing Analytics1. Go to "Events" → Click an event
2. Click the "Analytics" tab
3. See:
   - Total guests and check-in completion rate
   - Pie chart: breakdown by category
   - Bar chart: breakdown by location
   - Leaderboard: ambassador performance

### Viewing and Exporting Reports

1. Open **Reports** in the sidebar (or go to `/reports`).
2. Pick an event to open its infographic report: attendance, daily arrivals, guest mix, accreditation points, team performance, and the searchable guest list.
3. Select **Download Excel** to export that event as a six-sheet workbook: Summary, Daily attendance, Categories, Locations, Team, and Guests.
4. Use **Download overview** on the Reports page to export every event's summary into one workbook.

The Excel files are generated in the browser, so no download endpoint or extra server storage is required.

Admin API endpoints behind these screens (JWT required, admin role):

- `GET /api/admin/reports/` — summary for every event plus workspace totals.
- `GET /api/admin/events/{event_id}/report/` — full report for one event, including the guest list and custom guest fields.

Additional event and ambassador endpoints used by the dashboard:

- `PATCH /api/events/{event_id}/` — update event details, locations, and categories. Nested locations/categories accept optional `id` values; omitted rows are deactivated (soft-deleted) so historical records stay intact.
- `DELETE /api/admin/events/{event_id}/assign-bulk/` with `{"user_ids": [1, 2]}` — remove one or more ambassadors from an event.
- `DELETE /api/admin/ambassadors/{user_id}/` — permanently delete an ambassador.

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
2. They'll generate an API key for your event and send you the key plus the
   endpoint URL
3. The key is shown to the admin only once, so store it somewhere safe (e.g.
   a secrets manager) — it cannot be retrieved again, only replaced
4. Use this key in the `Authorization` header: `Bearer YOUR_API_KEY`

If your key is lost or compromised, ask the admin to revoke it and issue a
new one. Keys are limited to 90 requests per minute.

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

Up to 1000 guests per request — split larger lists into batches. Guests that
already exist (matching email, or name when no email is given) are not
duplicated; the response reports how many new records were created.

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
