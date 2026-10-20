# Guest Accreditation Platform - System Design & Architecture

## 📋 Executive Summary

A **multi-event, multi-user guest accreditation platform** built for brand activation companies. The system enables temporary brand ambassadors to check in guests at events using QR codes or manual search, with real-time visibility for admins and seamless integration with event organizers' systems.

### Core Value Proposition
- Event organizers push guest lists via REST API
- Admins configure events, assign ambassadors, and monitor live via web dashboard
- Ambassadors execute fast, reliable check-ins (even offline) via mobile app
- Real-time reporting via Google Sheets and admin dashboard
- Role-based access control with privacy-first data exposure

---

## 🎯 System Actors

| Actor | Interface | Primary Responsibilities |
|---|---|---|
| **Platform Owner** | Web Dashboard | Full system control, manage events, ambassadors, integrations |
| **Admin Staff** | Web Dashboard | Create events, configure custom fields, assign ambassadors, monitor live events |
| **Brand Ambassador** | Mobile App | Execute check-ins at assigned location during assigned shift |
| **Event Organizer** | REST API | Push guest lists to the platform programmatically |
| **Event Stakeholder** | Google Sheets (read-only) | View live attendance without logging in |

---

## 🌟 Core Features

### 1. Event Management
- Create events with start/end dates and per-day hour restrictions
- Define multiple accreditation locations per event (e.g., Lagos, Abuja, Airport)
- Configure guest categories (VIP, VVIP, Regular) with custom colors
- Build custom fields per event (schema stored as JSON, implemented in Phase 5)
- Set event logos, descriptions, and locations
- Per-day schedule support (e.g., Day 1: 8am-6pm, Day 2: 9am-3pm)

### 2. Ambassador Management
- Admin creates ambassador accounts (name, email, phone)
- System generates temporary password and sends welcome email
- Ambassador forced to change password on first login
- Admin assigns ambassadors to specific events (need-to-know access)
- Location assignment is fixed per shift (no mid-shift switching)
- Admin can deactivate ambassadors anytime

### 3. Guest Management
- Guests added exclusively via Organizer API (no manual entry in Phase 1-4)
- Each guest belongs to exactly one event
- Core fields: name, email, phone, ticket number, category, QR code
- Custom fields stored as JSON (flexible per event)
- Auto-generated unique ticket numbers and QR codes

### 4. Check-In Flow
1. Ambassador logs in → sees only assigned events
2. Selects event → auto-assigns location (if 1) or selects from list (if 2+)
3. Location is locked for the session
4. Scans QR code OR searches by name/ticket number
5. System validates: event active, within hours, not already checked in
6. On success: logs accreditation with ambassador ID + location + timestamp
7. Real-time update to Google Sheets + admin dashboard

### 5. Offline-First Architecture
- App caches guest list locally (SQLite) on event selection
- Offline check-ins validate against local DB
- Queued check-ins auto-sync when connection returns
- Server enforces UNIQUE constraint — first sync wins, second gets 409 Conflict
- Conflict shown to ambassador: "Already checked in by [Name] at [Time]"

### 6. Event Hour Enforcement
- Per-day schedule support (e.g., Day 1: 8am-6pm, Day 2: 9am-3pm)
- Admin can toggle enforcement off for flexibility
- Clear UI indication of current status (open/closed/upcoming)

### 7. Real-Time Reporting
- Google Sheets updated instantly on every check-in
- Excel export available per event (role-based data exposure)
- Admin dashboard with live metrics and charts

### 8. Organizer API
- API key authentication (separate from user auth)
- Bulk guest upload, single guest CRUD, status queries
- Rate limiting and audit logging
- Swagger/Redoc auto-generated documentation

---

## 🗄️ Data Model

### Core Entities

#### User
```
User (extends AbstractUser):
  - id (PK)
  - email (unique)
  - full_name
  - phone
  - role: choices=['admin', 'ambassador']
  - temp_password (hashed)
  - first_login: Boolean
  - is_active: Boolean
  - last_login: DateTime
  - created_at: DateTime
```

#### Event
```
Event:
  - id (PK)
  - name
  - description
  - logo (ImageField)
  - location (text, e.g., "Lagos, Nigeria")
  - start_date: DateTime
  - end_date: DateTime
  - daily_schedule: JSONField
    Example: {
      "2026-11-15": {"start": "08:00", "end": "18:00"},
      "2026-11-16": {"start": "09:00", "end": "15:00"}
    }
  - enforce_hours: Boolean
  - custom_fields_schema: JSONField (Phase 5)
  - is_active: Boolean
  - created_by: FK(User)
  - created_at: DateTime
```

#### Location
```
Location:
  - id (PK)
  - name (e.g., "Lagos", "Abuja", "Main Gate")
  - event: FK(Event)
  - description (optional)
  - is_active: Boolean
  - order: Integer (for display sorting)
```

#### GuestCategory
```
GuestCategory:
  - id (PK)
  - name (e.g., "VIP", "VVIP", "Regular")
  - event: FK(Event)
  - color: CharField (hex, e.g., "#FFD700")
  - priority: Integer (for sorting)
```

#### Guest
```
Guest:
  - id (PK)
  - event: FK(Event)
  - category: FK(GuestCategory, nullable)
  - adult_names: TextField
  - spouse_name: CharField
  - email: EmailField
  - phone: CharField
  - nanny_name: CharField
  - nanny_count: Integer
  - allergies: TextField
  - ticket_number: CharField (unique, auto-generated)
  - qr_code: ImageField
  - custom_data: JSONField (Phase 5)
  - created_at: DateTime
```

#### Kid
```
Kid:
  - id (PK)
  - guest: FK(Guest)
  - name: CharField
  - age: Integer
  - gender: CharField
```

#### Accreditation
```
Accreditation:
  - id (PK)
  - guest: FK(Guest)
  - event: FK(Event)
  - verified_by: FK(User)
  - location: FK(Location)
  - date: DateTime
  - time: TimeField
  - is_accredited: Boolean
  
  Meta:
    unique_together: (('guest', 'date'),)  # Prevents double check-in
    ordering: ['-date', '-time']
```

#### UserEventAccess
```
UserEventAccess:
  - id (PK)
  - user: FK(User)
  - event: FK(Event)
  - assigned_at: DateTime
  - assigned_by: FK(User)
  
  Meta:
    unique_together: (('user', 'event'),)
```

#### OrganizerAPIKey
```
OrganizerAPIKey:
  - id (PK)
  - key: CharField (unique)
  - organizer_name: CharField
  - event: FK(Event)
  - is_active: Boolean
  - created_at: DateTime
```

#### AuditLog
```
AuditLog:
  - id (PK)
  - user: FK(User, nullable)
  - action: CharField (e.g., "create_event", "check_in_guest")
  - resource_type: CharField (e.g., "Event", "Guest")
  - resource_id: Integer
  - details: JSONField
  - timestamp: DateTime
```

---

## 🏗️ Technical Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐   │
│   │  MOBILE APP     │    │  WEB DASHBOARD  │    │  ORGANIZER   │   │
│   │  React Native   │    │  Next.js        │    │  SYSTEMS     │   │
│   │  (Expo)         │    │  + Tailwind     │    │  (Any)       │   │
│   │                 │    │  + shadcn/ui    │    │              │   │
│   │  Ambassadors    │    │                 │    │  Via REST    │   │
│   │  + lite admin   │    │  Admins         │    │  API calls   │   │
│   └────────┬────────┘    └────────┬────────┘    └──────┬───────┘   │
│            │                      │                    │           │
└────────────┼──────────────────────┼────────────────────┼───────────┘
             │                      │                    │
             │    HTTPS + JWT       │   HTTPS + JWT      │ HTTPS + API Key
             │                      │                    │
             ▼                      ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DJANGO REST API (Render)                          │
│                                                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│   │ Auth Module  │  │ Event Module │  │ Check-In     │            │
│   │ JWT + Roles  │  │ + Locations  │  │ + Conflicts  │            │
│   └──────────────┘  └──────────────┘  └──────────────┘            │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│   │ Guest Module │  │ Organizer    │  │ Reporting    │            │
│   │ + Custom     │  │ API Module   │  │ Sheets+Excel │            │
│   └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
             │                      │                    │
             ▼                      ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA & SERVICES                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│   │ PostgreSQL   │  │ Cloudinary   │  │ Resend       │            │
│   │ (Render)     │  │ (Files/QR)   │  │ (Emails)     │            │
│   └──────────────┘  └──────────────┘  └──────────────┘            │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│   │ Google       │  │ Sentry       │  │ GitHub       │            │
│   │ Sheets API   │  │ (Errors)     │  │ (CI/CD)      │            │
│   └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Key User Flows

### Flow 1: Ambassador Check-In (Online)
```
Ambassador opens app
    → JWT validated → Home screen (assigned events only)
    → Selects event
    → Location auto-assigned (if 1) or selected (if 2+)
    → Fetches guest list → cached in local SQLite
    → Scans QR code OR searches name
    → POST /api/events/{id}/check-in/
    → Server validates (event active, hours ok, not duplicate)
    → Creates Accreditation record
    → Logs to Google Sheets
    → Returns success + guest details
    → Shows success modal (role-based data)
    → Updates activity log
```

### Flow 2: Ambassador Check-In (Offline)
```
Ambassador opens app (no internet)
    → Uses cached guest list from SQLite
    → Scans QR code
    → Validates against local DB (not already checked in locally)
    → Shows "Queued for Verification" modal
    → Writes to local pending_sync table
    → (Later) Internet returns
    → NetInfo listener triggers sync
    → Processes queue one by one
    → If 200 OK → remove from queue, update local DB
    → If 409 Conflict → mark as conflict, show error to user
    → If network error → keep in queue, retry later
```

### Flow 3: Admin Creates Event
```
Admin logs into web dashboard
    → Clicks "Create Event"
    → Fills: name, dates, description, location, logo
    → Configures per-day schedule (JSON)
    → Toggles hour enforcement
    → Adds locations (e.g., "Lagos", "Abuja")
    → Defines guest categories
    → (Phase 5) Builds custom field schema
    → Saves → Event created in database
    → Assigns ambassadors to event
    → System generates access records
```

### Flow 4: Organizer Pushes Guest List
```
Organizer has guest list in their system
    → POST /api/organizers/events/{id}/guests/bulk/
    → Headers: Authorization: Bearer org_abc123
    → Body: JSON array of guests
    → Server validates API key + rate limit
    → Creates Guest records + auto-generates ticket numbers + QR codes
    → Returns success with guest IDs
    → Audit log entry created
```

### Flow 5: Ambassador Onboarding
```
Admin creates ambassador account
    → Enters name, email, phone
    → System generates temp password
    → Sends welcome email via Resend
    → Ambassador receives email with login link + temp password
    → Logs in → forced to change password
    → Admin assigns ambassador to events
    → Ambassador sees only assigned events on next login
```

---

## 🔐 Security & Privacy Model

### Authentication
- **Mobile + Web:** JWT tokens (access token 15min, refresh token 7 days)
- **Organizer API:** Long-lived API keys (revocable)
- **Password storage:** bcrypt hashing
- **First login:** Forced password change for ambassadors

### Authorization (Role-Based)

| Action | Admin | Ambassador | Organizer API |
|---|---|---|---|
| Create/edit events | ✅ | ❌ | ❌ |
| Manage ambassadors | ✅ | ❌ | ❌ |
| View full guest data | ✅ | ❌ | ❌ |
| Check in guests | ✅ | ✅ (assigned events only) | ❌ |
| View limited guest data | ✅ | ✅ (name + category only) | ❌ |
| Push guest lists | ❌ | ❌ | ✅ (assigned events only) |
| View analytics | ✅ | ❌ | ❌ |

### Data Privacy
- **Ambassadors see:** name, category, kids count, check-in status
- **Admins see:** everything (email, phone, spouse, nanny, custom fields)
- **Organizer API sees:** only what they push (their own guests)
- **Google Sheets:** limited columns (name, category, kids, verified by, time)

### Access Control
- **Need-to-know events:** Ambassador sees ONLY events they're assigned to
- **Location lock:** Ambassador cannot change location mid-shift
- **Event hours:** Enforced server-side, admin can override
- **Account deactivation:** Admin can disable ambassador instantly

---

## 📡 API Design

### Public Auth Endpoints
- `POST /api/auth/login/` — Login, returns JWT tokens
- `POST /api/auth/refresh/` — Refresh JWT access token
- `POST /api/auth/change-password/` — Change password (first login)

### Admin Endpoints (Web Dashboard)
- Events CRUD: `/api/admin/events/`
- Locations CRUD: `/api/admin/events/{id}/locations/`
- Categories CRUD: `/api/admin/events/{id}/categories/`
- Ambassadors CRUD: `/api/admin/ambassadors/`
- Event assignments: `/api/admin/events/{id}/assignments/`
- Analytics: `/api/admin/analytics/events/{id}/`
- Audit logs: `/api/admin/audit-logs/`

### Ambassador Endpoints (Mobile App)
- `GET /api/events/` — List events (filtered by access)
- `GET /api/events/{id}/locations/` — Get locations for event
- `GET /api/events/{id}/guests/` — List guests (summary serializer)
- `GET /api/events/{id}/guests/{id}/` — Get guest details (summary)
- `POST /api/events/{id}/check-in/` — Check in guest
- `GET /api/events/{id}/activity-log/` — Get activity log
- `GET /api/events/{id}/search-guests/?q=` — Search guests by name

### Organizer API Endpoints
- `POST /api/organizers/events/{id}/guests/bulk/` — Bulk upload guests
- `POST /api/organizers/events/{id}/guests/` — Add single guest
- `PUT /api/organizers/events/{id}/guests/{id}/` — Update guest
- `DELETE /api/organizers/events/{id}/guests/{id}/` — Remove guest
- `GET /api/organizers/events/{id}/status/` — Get check-in stats
- `GET /api/organizers/events/{id}/guests/{id}/status/` — Check guest status

### API Documentation
- Auto-generated via DRF Spectacular (OpenAPI 3.0)
- Available at `/api/docs/` (Swagger UI) and `/api/redoc/`

---

## 🖥️ Admin Dashboard (Web)

### Essential Metrics
- Active events list with real-time check-in counts
- Check-in rate per hour (per event)
- Ambassador activity (who's checking in, who's idle)
- Conflict alerts (double check-in attempts)
- Pending sync count (network issues)
- Guest list completion percentage
- Location breakdown (check-ins per location)

### Nice-to-Have Metrics
- Peak check-in times (historical)
- Category breakdown (VIP/VVIP/Regular)
- Average check-in time per ambassador
- Comparison to past events
- Predicted completion time
- No-show list
- Ambassador leaderboard
- Heat map by time
- Custom field aggregates (e.g., dietary counts)

### Admin Capabilities
- Event CRUD with per-day schedule builder
- Custom field schema builder (Phase 5)
- Ambassador account management
- Event-ambassador assignments
- API key management for organizers
- Google Sheets integration config
- Audit log viewer
- Report exports

---

## 📱 Mobile App (Ambassador)

### Screens
1. **Splash** — Check JWT, route to Login or Home
2. **Login** — Email + password
3. **Change Password** — Forced on first login
4. **Home** — List of assigned events (with status: upcoming/live/ended)
5. **Location Selection** — Only if event has 2+ locations
6. **Check-In** — Scanner + manual search + activity log
7. **Success/Denial Modal** — Role-based guest details
8. **Settings** — Logout, about, version

### Offline Capabilities
- SQLite local database for guest list cache
- Pending sync queue for offline check-ins
- NetInfo listener for auto-sync
- Visual indicators: network status, pending count
- Conflict resolution UI

### Design Principles (Emil Kowalski)
- Subtle micro-interactions (Pressable scale/opacity)
- Smooth modal animations (200ms, bezier easing)
- Reduced motion accessibility respected
- Fast-feeling (no blocking animations)
- Clear visual hierarchy with purposeful color coding

---

## 🌐 Hosting & Infrastructure

| Component | Provider | Plan | Purpose |
|---|---|---|---|
| Django API | Render | $7/mo | Backend hosting |
| PostgreSQL | Render | $7/mo | Database |
| Mobile App | EAS Build (Expo) | Free tier | iOS/Android builds |
| Web Dashboard | Vercel | Free tier | Admin dashboard hosting |
| File Storage | Cloudinary | Free (25GB) | Logos, QR codes |
| Email | Resend | Free (3k/mo) | Welcome emails, password resets |
| Google Sheets | Google Cloud | Free | Real-time reporting |
| Error Tracking | Sentry | Free (5k events) | Production error monitoring |
| Domain | Namecheap | ~$12/yr | Custom domain |
| Code Hosting | GitHub | Free | Version control + CI/CD |

**Total monthly cost:** ~$15/month for production

### Environment Variables (Render)
```
DATABASE_URL
DJANGO_SECRET_KEY
CLOUDINARY_URL
RESEND_API_KEY
GOOGLE_SHEETS_CREDENTIALS
GOOGLE_SHEET_ID
ALLOWED_HOSTS
DEBUG=False
FRONTEND_URL
```

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal:** Authentication + User management + Basic event structure

- Custom User model with roles
- JWT authentication (login, refresh, change password)
- Event model with per-day schedule
- Location model
- Category model
- UserEventAccess model
- Admin creates ambassador accounts
- Welcome email flow with temp password
- Basic web dashboard (login + event list)
- Basic mobile app (login + event list)

### Phase 2: Core Check-In (Week 3-4)
**Goal:** Working check-in flow for ambassadors

- Guest model (core fields only)
- Kid model
- Accreditation model with UNIQUE constraint
- Organizer API key model
- Organizer API endpoints (bulk guest upload)
- QR code auto-generation
- Check-in endpoint with validation
- Location selection flow (mobile)
- Activity log
- Basic Google Sheets integration

### Phase 3: Offline & Conflicts (Week 5)
**Goal:** Robust offline-first experience

- SQLite integration in mobile app
- Local guest list caching
- Pending sync queue
- Auto-sync on network recovery
- Conflict resolution UI
- Network status indicators
- Pending count badge

### Phase 4: Admin Dashboard (Week 6-7)
**Goal:** Full admin capabilities

- Event CRUD with per-day schedule builder
- Location management
- Category management
- Ambassador management (CRUD + assignments)
- Real-time analytics
- Activity monitoring
- Conflict alerts
- Report exports (Excel)

### Phase 5: Polish & Launch (Week 8)
**Goal:** Production-ready system

- Custom field schema builder
- Error handling hardening
- Sentry integration
- Uptime monitoring
- API documentation (Swagger)
- Security audit
- Performance optimization
- User documentation
- Deployment checklist

---

## 📊 Success Metrics

| Metric | Target |
|---|---|
| Check-in latency (online) | < 500ms |
| Check-in latency (offline sync) | < 2s after reconnect |
| Conflict rate | < 1% of total check-ins |
| API uptime | 99.9% |
| Ambassador onboarding time | < 5 minutes |
| Event setup time (admin) | < 10 minutes |
| Organizer API integration time | < 1 hour |

---

## 🎯 Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Database | Single PostgreSQL | Simple, scalable, standard |
| Custom fields | JSONField per event | Flexible, no migrations needed |
| Ambassador onboarding | Admin-created accounts | Maximum security |
| Event access | Need-to-know (assignment-based) | Prevents unauthorized access |
| Location switching | Fixed per shift | Operational clarity |
| Guest source | Organizer API only | Single source of truth |
| Admin interface | Web dashboard (separate) | Better for complex tasks |
| Conflict resolution | Server UNIQUE constraint | Bulletproof, first-sync-wins |
| Hour enforcement | Per-day schedule + toggle | Flexible but controlled |
| Data privacy | Two serializers by role | Ambassadors see limited data |

---

## 📝 Document Version

- **Version:** 1.0
- **Last Updated:** 2026-10-15
- **Status:** Approved for Implementation
- **Next Phase:** Phase 1 - Foundation