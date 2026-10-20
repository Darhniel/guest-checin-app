# Agent Implementation Guide - Guest Accreditation Platform

## 🎯 Purpose

This guide provides strict rules, constraints, and step-by-step instructions for AI agents implementing the Guest Accreditation Platform. Follow this guide to ensure consistency, security, and alignment with the system design.

---

## 📚 Reference Documents

**Always consult these before writing code:**
- `SYSTEM_DESIGN.md` — Complete system architecture and data models
- This guide (`AGENT_GUIDE.md`) — Implementation rules and workflows

---

## 🚨 CRITICAL RULES (Never Violate)

### Rule 1: Security First
- **NEVER** store passwords in plain text — always use Django's built-in hashing
- **NEVER** expose sensitive guest data (email, phone, spouse) to ambassadors — use role-based serializers
- **NEVER** allow ambassadors to access events they're not assigned to — enforce UserEventAccess checks
- **NEVER** disable the UNIQUE constraint on Accreditation (guest, date) — this prevents double check-ins
- **NEVER** commit environment variables or API keys to GitHub

### Rule 2: Offline-First Architecture
- **ALWAYS** validate check-ins against local SQLite when offline
- **ALWAYS** queue offline check-ins in pending_sync table
- **ALWAYS** auto-sync when network returns (NetInfo listener)
- **ALWAYS** handle 409 Conflict responses gracefully — show user-friendly error
- **NEVER** allow offline check-ins to bypass server validation

### Rule 3: Role-Based Access Control
- **Admin role:** Full access to all data and operations
- **Ambassador role:** Limited access — only assigned events, limited guest data
- **Organizer API:** Only access to events they have API keys for
- **ALWAYS** check `request.user.role` before returning data
- **ALWAYS** use appropriate serializer (GuestSummarySerializer vs GuestDetailSerializer)

### Rule 4: Data Privacy
- **Ambassadors see:** name, category, kids_count, check-in status ONLY
- **Admins see:** everything (email, phone, spouse, nanny, custom fields)
- **NEVER** return full guest data to ambassadors — even if they "need it"
- **ALWAYS** log data access in AuditLog for compliance

### Rule 5: Event Hour Enforcement
- **ALWAYS** check event hours before allowing check-in
- **ALWAYS** respect per-day schedule (if enforce_hours=True)
- **ALWAYS** allow admin override (toggle enforce_hours off)
- **NEVER** hardcode hours — read from Event.daily_schedule JSON

---

## 🏗️ Project Structure

### Backend (Django)
```
guest-accreditation-platform/
├── core/                      # Main Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accreditation/             # Main app
│   ├── models.py              # All data models
│   ├── serializers.py         # DRF serializers (role-based)
│   ├── views.py               # API views
│   ├── urls.py                # API routes
│   ├── admin.py               # Django admin config
│   ├── permissions.py         # Custom permissions
│   ├── sheets.py              # Google Sheets integration
│   └── utils.py               # Helper functions
├── manage.py
├── requirements.txt
├── Procfile
├── runtime.txt
└── .gitignore
```

### Mobile App (React Native)
```
mobile-app/
├── src/
│   ├── screens/
│   │   ├── LoginScreen.tsx
│   │   ├── ChangePasswordScreen.tsx
│   │   ├── HomeScreen.tsx
│   │   ├── LocationSelectionScreen.tsx
│   │   ├── CheckInScreen.tsx
│   │   └── SettingsScreen.tsx
│   ├── components/
│   │   ├── QRScanner.tsx
│   │   ├── GuestCard.tsx
│   │   ├── ActivityLog.tsx
│   │   └── ResultModal.tsx
│   ├── services/
│   │   ├── api.ts             # API client
│   │   ├── auth.ts            # JWT management
│   │   ├── database.ts        # SQLite operations
│   │   └── sync.ts            # Offline sync logic
│   ├── types/
│   │   └── index.ts           # TypeScript interfaces
│   └── utils/
│       ├── date.ts            # Date formatting
│       └── validation.ts      # Input validation
├── App.tsx
└── package.json
```

### Web Dashboard (Next.js)
```
web-dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           # Dashboard home
│   │   ├── events/
│   │   │   ├── page.tsx       # Events list
│   │   │   └── [id]/
│   │   │       ├── page.tsx   # Event detail
│   │   │       └── analytics/
│   │   │           └── page.tsx
│   │   ├── ambassadors/
│   │   │   └── page.tsx
│   │   └── settings/
│   │       └── page.tsx
│   ├── components/
│   │   ├── ui/                # shadcn/ui components
│   │   ├── EventCard.tsx
│   │   ├── AmbassadorTable.tsx
│   │   └── AnalyticsChart.tsx
│   ├── lib/
│   │   ├── api.ts             # API client
│   │   └── utils.ts
│   └── types/
│       └── index.ts
├── package.json
└── next.config.js
```

---

## 📋 Implementation Checklist

### Phase 1: Foundation (Week 1-2)

#### Backend Tasks
- [ ] Create Django project structure
- [ ] Install dependencies: `djangorestframework`, `djangorestframework-simplejwt`, `django-cors-headers`, `dj-database-url`, `whitenoise`, `gunicorn`, `qrcode`, `Pillow`, `gspread`, `google-auth`, `resend`
- [ ] Create custom User model with `role` field
- [ ] Configure JWT authentication (access 15min, refresh 7 days)
- [ ] Create Event model with `daily_schedule` JSONField
- [ ] Create Location model
- [ ] Create GuestCategory model
- [ ] Create UserEventAccess model
- [ ] Create AuditLog model
- [ ] Implement auth endpoints: `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/change-password/`
- [ ] Implement admin endpoints: `/api/admin/events/`, `/api/admin/ambassadors/`
- [ ] Create welcome email template (Resend)
- [ ] Implement temp password generation
- [ ] Add CORS configuration
- [ ] Set up environment variables
- [ ] Deploy to Render (web service + PostgreSQL)

#### Mobile App Tasks
- [ ] Initialize Expo project with TypeScript
- [ ] Install dependencies: `expo-camera`, `expo-secure-store`, `expo-sqlite`, `@react-native-async-storage/async-storage`, `@react-native-community/netinfo`
- [ ] Create Login screen
- [ ] Create ChangePassword screen (forced on first login)
- [ ] Create Home screen (events list)
- [ ] Implement JWT token storage (expo-secure-store)
- [ ] Implement auto-login on app open
- [ ] Implement token refresh logic
- [ ] Create API client with JWT headers
- [ ] Test login flow end-to-end

#### Web Dashboard Tasks
- [ ] Initialize Next.js project with TypeScript
- [ ] Install shadcn/ui + Tailwind CSS
- [ ] Create Login page
- [ ] Create Dashboard layout (sidebar + main content)
- [ ] Create Events list page
- [ ] Implement JWT token storage (localStorage)
- [ ] Create API client with JWT headers
- [ ] Test login flow end-to-end

### Phase 2: Core Check-In (Week 3-4)

#### Backend Tasks
- [ ] Create Guest model (core fields)
- [ ] Create Kid model
- [ ] Create Accreditation model with UNIQUE constraint
- [ ] Create OrganizerAPIKey model
- [ ] Create GuestSummarySerializer (limited fields)
- [ ] Create GuestDetailSerializer (full fields)
- [ ] Implement role-based serializer selection in views
- [ ] Implement check-in endpoint: `/api/events/{id}/check-in/`
- [ ] Add event hour validation in check-in view
- [ ] Add duplicate check-in prevention (UNIQUE constraint)
- [ ] Implement activity log endpoint: `/api/events/{id}/activity-log/`
- [ ] Implement search endpoint: `/api/events/{id}/search-guests/`
- [ ] Create Organizer API endpoints: `/api/organizers/events/{id}/guests/bulk/`
- [ ] Implement QR code auto-generation
- [ ] Implement Google Sheets integration (sheets.py)
- [ ] Add audit logging for all write operations
- [ ] Test check-in flow end-to-end

#### Mobile App Tasks
- [ ] Create LocationSelection screen (conditional: only if 2+ locations)
- [ ] Create CheckIn screen (scanner + manual search)
- [ ] Implement QR scanner with expo-camera
- [ ] Implement manual search with debounced API call
- [ ] Create ResultModal (role-based guest details)
- [ ] Implement activity log display
- [ ] Add network status indicator
- [ ] Test check-in flow end-to-end

### Phase 3: Offline & Conflicts (Week 5)

#### Mobile App Tasks
- [ ] Integrate expo-sqlite
- [ ] Create local database schema: `local_guests`, `pending_checkins`
- [ ] Implement auto-sync on app open (fetch guest list when online)
- [ ] Implement offline check-in (validate against local DB)
- [ ] Implement queue system (pending_checkins table)
- [ ] Implement background sync (process queue when online)
- [ ] Implement conflict handling (show error when 409 received)
- [ ] Add "Pending" badge to UI
- [ ] Test offline flow end-to-end
- [ ] Test conflict resolution scenario

### Phase 4: Admin Dashboard (Week 6-7)

#### Web Dashboard Tasks
- [ ] Create Event CRUD pages (create, edit, delete)
- [ ] Build per-day schedule editor (JSON)
- [ ] Create Location management UI
- [ ] Create Category management UI
- [ ] Create Ambassador management UI (CRUD + assignments)
- [ ] Build real-time analytics dashboard
- [ ] Implement activity monitoring
- [ ] Add conflict alerts
- [ ] Create report export functionality (Excel)
- [ ] Test admin workflows end-to-end

### Phase 5: Polish & Launch (Week 8)

#### All Tasks
- [ ] Implement custom field schema builder (Phase 5 feature)
- [ ] Add error handling hardening
- [ ] Integrate Sentry for error tracking
- [ ] Set up UptimeRobot monitoring
- [ ] Generate API documentation (DRF Spectacular)
- [ ] Perform security audit
- [ ] Optimize performance (queries, caching)
- [ ] Write user documentation
- [ ] Create deployment checklist
- [ ] Final testing (all flows)
- [ ] Launch!

---

## 🎨 Design Guidelines

### Mobile App (Emil Kowalski Principles)
- **DO:** Use subtle micro-interactions (Pressable scale 0.97, opacity 0.75)
- **DO:** Use smooth modal animations (200ms, bezier easing)
- **DO:** Respect `prefers-reduced-motion` accessibility setting
- **DO:** Use clear visual hierarchy (purposeful color coding)
- **DON'T:** Use large dramatic animations
- **DON'T:** Animate every element
- **DON'T:** Use excessive bouncing
- **DON'T:** Use long transitions (>300ms)
- **DON'T:** Delay interaction with animations

### Color Palette
```typescript
const C = {
  success: "#22C55E",
  error: "#E55353",
  warning: "#F59E0B",
  textPrimary: "#111827",
  textSecondary: "#6B7280",
  textMuted: "#9CA3AF",
  cardBg: "#FFFFFF",
  cardBorder: "#E5E7EB",
  pageBg: "#F3F4F6",
  accent: "#2563EB",
};
```

### Web Dashboard
- **Framework:** Next.js 14+ with App Router
- **UI Library:** shadcn/ui (Tailwind-based)
- **Charts:** Recharts or Chart.js
- **Tables:** TanStack Table
- **Forms:** React Hook Form + Zod validation

---

## 🔐 Security Checklist

### Before Deployment
- [ ] All passwords hashed with bcrypt
- [ ] JWT tokens stored securely (expo-secure-store on mobile, httpOnly cookies on web)
- [ ] CORS configured correctly (only allow your domains)
- [ ] Environment variables not in code
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enforced
- [ ] Rate limiting on API endpoints
- [ ] Audit logging enabled
- [ ] Role-based access control tested

### Ongoing
- [ ] Monitor Sentry for errors
- [ ] Review audit logs weekly
- [ ] Rotate API keys quarterly
- [ ] Update dependencies monthly
- [ ] Backup database daily (Render automatic)

---

## 🧪 Testing Strategy

### Backend Tests
```python
# Test authentication
def test_login_success():
def test_login_wrong_password():
def test_refresh_token():
def test_change_password_first_login():

# Test role-based access
def test_admin_can_view_all_guest_data():
def test_ambassador_can_only_view_assigned_events():
def test_ambassador_cannot_view_guest_email():

# Test check-in flow
def test_check_in_success():
def test_check_in_duplicate_rejected():
def test_check_in_outside_hours_rejected():
def test_check_in_event_ended_rejected():

# Test offline sync
def test_offline_check_in_queued():
def test_sync_success_removes_from_queue():
def test_sync_conflict_shows_error():
```

### Mobile App Tests
```typescript
// Test authentication
test('login with valid credentials succeeds');
test('login with invalid credentials fails');
test('first login forces password change');

// Test check-in flow
test('scan QR code triggers check-in');
test('manual search shows dropdown');
test('offline check-in queues locally');
test('sync processes queue when online');

// Test role-based UI
test('ambassador sees limited guest data');
test('admin sees full guest data');
```

---

## 📝 Code Style Guidelines

### Backend (Python/Django)
- Follow PEP 8
- Use type hints
- Docstrings for all functions
- Max line length: 100 characters
- Use f-strings for string formatting
- Prefer list comprehensions over loops

### Mobile App (TypeScript/React Native)
- Strict TypeScript (no `any` unless absolutely necessary)
- Functional components with hooks
- Extract reusable components
- Use React Navigation for routing
- Prefer async/await over .then()

### Web Dashboard (TypeScript/Next.js)
- Strict TypeScript
- Server components where possible
- Client components only when needed (interactivity)
- Use shadcn/ui components
- Follow Next.js App Router conventions

---

## 🚀 Deployment Checklist

### Backend (Render)
- [ ] Code pushed to GitHub
- [ ] Render connected to GitHub repo
- [ ] Environment variables set
- [ ] Database migrations run
- [ ] Static files collected
- [ ] Superuser created
- [ ] API endpoints tested
- [ ] CORS configured
- [ ] HTTPS enforced

### Mobile App (EAS Build)
- [ ] Code pushed to GitHub
- [ ] EAS configured
- [ ] Build profiles set (development, preview, production)
- [ ] APK/IPA generated
- [ ] Tested on physical devices
- [ ] Push notifications configured (if needed)

### Web Dashboard (Vercel)
- [ ] Code pushed to GitHub
- [ ] Vercel connected to GitHub repo
- [ ] Environment variables set
- [ ] Build succeeds
- [ ] Deployed to production
- [ ] Custom domain configured (optional)

---

## 🐛 Common Pitfalls & Solutions

### Pitfall 1: Ambassador sees full guest data
**Problem:** Ambassador can see email, phone, spouse info
**Solution:** Check `request.user.role` in view, use GuestSummarySerializer for ambassadors

### Pitfall 2: Offline check-in allows duplicates
**Problem:** Two ambassadors check in same guest offline, both succeed locally
**Solution:** Server UNIQUE constraint catches it on sync, show conflict error to second user

### Pitfall 3: Event hours not enforced
**Problem:** Ambassador checks in guest outside event hours
**Solution:** Add hour validation in check-in view, check Event.daily_schedule

### Pitfall 4: Ambassador accesses unassigned event
**Problem:** Ambassador sees events they're not assigned to
**Solution:** Filter events by UserEventAccess in queryset

### Pitfall 5: QR code not generated
**Problem:** Guest created but no QR code image
**Solution:** Ensure `save()` method generates QR code, check MEDIA_ROOT permissions

---

## 📞 Escalation Path

If you encounter issues:
1. Check `SYSTEM_DESIGN.md` for architecture guidance
2. Review this guide for implementation rules
3. Check Django/React Native documentation
4. Test with minimal reproduction
5. If still stuck, document the issue and propose solutions

---

## ✅ Success Criteria

The implementation is successful when:
- [ ] Ambassadors can log in and see only assigned events
- [ ] Ambassadors can scan QR codes and check in guests
- [ ] Offline check-ins queue and sync correctly
- [ ] Conflicts are detected and shown to users
- [ ] Admins can create events and assign ambassadors
- [ ] Admins can view real-time analytics
- [ ] Organizers can push guest lists via API
- [ ] Google Sheets updates in real-time
- [ ] All security rules are enforced
- [ ] Performance targets are met (<500ms check-in latency)

---

## 📄 Document Version

- **Version:** 1.0
- **Last Updated:** 2026-10-15
- **Status:** Active
- **Next Review:** After Phase 1 completion
</parameter>
</function>
</function_calls>