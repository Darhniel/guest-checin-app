from rest_framework import generics, status, permissions, exceptions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from .models import (
    generate_api_key,
    hash_api_key,
    CustomUser,
    Event,
    Location,
    GuestCategory,
    UserEventAccess,
)
from .serializers import (
    UserSerializer, UserCreateSerializer, EventSerializer, 
    LocationSerializer, GuestCategorySerializer, OrganizerGuestSerializer,
    OrganizerAPIKeySerializer, AdminGuestCreateSerializer,
)
from django.utils import timezone
from django.db.models import Q, Count
from django.db.models.functions import TruncHour
from django.core.cache import cache
import hashlib
from rest_framework.permissions import AllowAny
from .models import Guest, Kid, Accreditation, OrganizerAPIKey, AuditLog
from .serializers import GuestSummarySerializer, GuestDetailSerializer, AccreditationSerializer
import logging
from datetime import datetime, time, timedelta
from rest_framework.views import APIView
from .validators import validate_custom_data
from .throttles import LoginThrottle

logger = logging.getLogger(__name__)

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginThrottle]
    
    def post(self, request, *args, **kwargs):
        # SimpleJWT expects 'username', we map it to 'email'
        if 'email' in request.data:
            request.data['username'] = request.data['email']
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.get(email=request.data.get('email'))
            response.data['user'] = UserSerializer(user).data
        return response

class ChangePasswordView(generics.UpdateAPIView):
    # authentication_classes = []
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def update(self, request, *args, **kwargs):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not user.check_password(old_password):
            return Response({'error': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)

        if not new_password or len(new_password) < 8:
            return Response(
                {'error': 'The new password must be at least 8 characters.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.first_login = False
        user.save()
        return Response({'message': 'Password updated successfully.'}, status=status.HTTP_200_OK)

class EventGuestsListView(generics.ListAPIView):
    """Returns all guests for an event (used for offline caching)"""
    serializer_class = GuestSummarySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        return Guest.objects.filter(event_id=event_id).order_by('names')
    
class EventListView(generics.ListCreateAPIView):
    serializer_class = EventSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        queryset = Event.objects.select_related('created_by').prefetch_related(
            'locations', 'categories'
        )

        if user.role == 'admin':
            return queryset.order_by('-start_date')
        return queryset.filter(user_access__user=user).order_by('-start_date')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Event.objects.all()
        return Event.objects.filter(user_access__user=user)

class LocationListView(generics.ListCreateAPIView):
    serializer_class = LocationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        return Location.objects.filter(event_id=event_id, is_active=True).order_by('order')

    def perform_create(self, serializer):
        event_id = self.kwargs.get('event_id')
        serializer.save(event_id=event_id)

class CategoryListView(generics.ListCreateAPIView):
    serializer_class = GuestCategorySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        return GuestCategory.objects.filter(
            event_id=event_id, is_active=True
        ).order_by('-priority')

    def perform_create(self, serializer):
        event_id = self.kwargs.get('event_id')
        serializer.save(event_id=event_id)

class AmbassadorCreateView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # TODO: Phase 2 - Send welcome email with temp password here
        
        return Response({
            'message': 'Ambassador created successfully.',
            'user': UserSerializer(user).data,
            'temp_password': request.data.get('password') 
        }, status=status.HTTP_201_CREATED)

class AssignAmbassadorView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        user_id = request.data.get('user_id')
        event_id = request.data.get('event_id')

        if not user_id or not event_id:
            return Response({'error': 'user_id and event_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        access, created = UserEventAccess.objects.get_or_create(
            user_id=user_id,
            event_id=event_id,
            defaults={'assigned_by': request.user}
        )

        if created:
            return Response({'message': 'Ambassador assigned to event successfully.'}, status=status.HTTP_201_CREATED)
        return Response({'message': 'Ambassador already has access to this event.'}, status=status.HTTP_200_OK)

# ==========================================
# CHECK-IN & SEARCH VIEWS
# ==========================================

class CheckInView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        identifier = request.data.get('identifier', '').strip()
        location_id = request.data.get('location_id')

        if not identifier:
            return Response({'status': 400, 'message': 'Please provide ticket number or name'}, status=400)

        # 1. Find Guest
        guest = Guest.objects.filter(
            Q(names__iexact=identifier) | Q(ticket_number__iexact=identifier),
            event_id=event_id
        ).first()

        if not guest:
            return Response(
                {'status': 404, 'message': 'This is not a registered guest for this event'}, 
                status=404,
                content_type='application/json'
            )

        # 2. Validate Event Hours
        event = guest.event
        today_str = timezone.localdate().isoformat()
        now = timezone.localtime()
        
        if event.enforce_hours and event.daily_schedule:
            schedule = event.daily_schedule.get(today_str)
            if schedule:
                start_dt = timezone.datetime.strptime(schedule['start'], '%H:%M').replace(
                    year=today.year, month=today.month, day=today.day
                )
                start_time = timezone.make_aware(start_dt)
                end_dt = timezone.datetime.strptime(schedule['end'], '%H:%M').replace(
                    year=today.year, month=today.month, day=today.day
                )
                end_time = timezone.make_aware(end_dt)
                
                if not (start_time <= now <= end_time):
                    return Response({
                        'status': 403, 
                        'message': f'Check-ins are only allowed between {schedule["start"]} and {schedule["end"]} today.'
                    }, status=403)

        # 3. Check for Duplicate (UNIQUE constraint will also catch this, but we want a friendly message)
        today = timezone.localdate()
        if Accreditation.objects.filter(guest=guest, date=today, is_accredited=True).exists():
            existing = Accreditation.objects.filter(guest=guest, date=today, is_accredited=True).first()
            verifier = existing.verified_by.full_name if existing.verified_by else "Unknown"
            return Response({
                'status': 409, 
                'message': f'Already checked in today by {verifier} at {existing.time.strftime("%I:%M %p")}'
            }, status=409, content_type='application/json')

        # 4. Validate location if provided
        location = None
        if location_id and location_id != 0:
            try:
                location = Location.objects.get(id=location_id, event=event, is_active=True)
            except Location.DoesNotExist:
                return Response({
                    'status': 400, 
                    'message': 'Invalid location for this event'
                }, status=400)
    
        # 5. Create Accreditation
        accreditation = Accreditation.objects.create(
            guest=guest,
            event=event,
            verified_by=request.user,
            location=location,
            is_accredited=True
        )

        # 6. Audit Log
        AuditLog.objects.create(
            user=request.user,
            action='check_in',
            resource_type='Accreditation',
            resource_id=accreditation.id,
            details={'guest_id': guest.id, 'event_id': event.id}
        )

        # 7. Return appropriate serializer based on role
        if request.user.role == 'admin':
            guest_serializer = GuestDetailSerializer(guest)
        else:
            guest_serializer = GuestSummarySerializer(guest)

        # TODO: Phase 4 - Trigger Google Sheets logging here

        return Response({
            'status': 200,
            'message': 'Guest successfully accredited.',
            'guest': guest_serializer.data
        }, status=200)

class ActivityLogView(generics.ListAPIView):
    serializer_class = AccreditationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        today = timezone.localdate()
        return Accreditation.objects.filter(event_id=event_id, date=today).order_by('-time')[:50]

class SearchGuestsView(generics.ListAPIView):
    serializer_class = GuestSummarySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        query = self.request.query_params.get('q', '').strip()
        
        if len(query) < 3:
            return Guest.objects.none()

        today = timezone.localdate()
        accredited_ids = set(
            Accreditation.objects.filter(event_id=event_id, date=today, is_accredited=True)
            .values_list('guest_id', flat=True)
        )

        guests = Guest.objects.filter(
            event_id=event_id,
            names__icontains=query
        ).order_by('names')[:10]

        # Annotate with checked-in status for the UI
        for guest in guests:
            guest.is_checked_in_today = guest.id in accredited_ids
            
        return guests

# ==========================================
# ORGANIZER API VIEWS
# ==========================================

class OrganizerPermission(permissions.BasePermission):
    """
    Auth for event organizers. Each key unlocks ingestion for exactly one
    event. Keys are compared by SHA-256 digest, and failed lookups are
    rate limited per IP to slow down key-guessing.
    """

    MAX_REQUESTS_PER_MINUTE = 90

    def has_permission(self, request, view):
        self._throttle(request)

        api_key = request.headers.get('Authorization')
        if not api_key or not api_key.startswith('Bearer '):
            return False

        key_value = api_key.split(' ', 1)[1].strip()
        key_hash = hash_api_key(key_value)
        try:
            request.organizer_key = OrganizerAPIKey.objects.select_related(
                'event'
            ).get(key_hash=key_hash, is_active=True)
            # Update last used
            request.organizer_key.last_used = timezone.now()
            request.organizer_key.save(update_fields=['last_used'])
            return True
        except OrganizerAPIKey.DoesNotExist:
            return False

    def _throttle(self, request):
        ident = request.META.get('REMOTE_ADDR') or 'unknown'
        # Accept proxies we control; header spoofing is handled upstream.
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            ident = forwarded.split(',')[0].strip() or ident

        cache_key = f'organizer_key_throttle:{ident}'
        count = cache.get(cache_key)
        if count is None:
            cache.add(cache_key, 1, 60)
            return
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.add(cache_key, 1, 60)
            return
        if count > self.MAX_REQUESTS_PER_MINUTE:
            raise exceptions.Throttled(
                detail='Too many requests from your IP. Try again shortly.'
            )

class AdminDashboardStatsView(generics.RetrieveAPIView):
    """Overall stats for the admin dashboard"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        today = timezone.localdate()
        active_events = Event.objects.filter(is_active=True, end_date__gte=today).count()
        total_guests = Guest.objects.count()
        today_checkins = Accreditation.objects.filter(date=today, is_accredited=True).count()
        total_ambassadors = CustomUser.objects.filter(role='ambassador', is_active=True).count()

        # Check-ins per hour today (for chart)
        hourly = Accreditation.objects.filter(
            date=today, is_accredited=True
        ).annotate(
            hour=TruncHour('time')
        ).values('hour').annotate(count=Count('id')).order_by('hour')

        return Response({
            'active_events': active_events,
            'total_guests': total_guests,
            'today_checkins': today_checkins,
            'total_ambassadors': total_ambassadors,
            'hourly_checkins': list(hourly),
        })


class AdminAmbassadorListView(generics.ListAPIView):
    """List all ambassadors (admin only)"""
    from .serializers import UserSerializer
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return CustomUser.objects.none()
        return CustomUser.objects.filter(role='ambassador').order_by('-date_joined')


class AdminAmbassadorToggleView(generics.UpdateAPIView):
    """Activate/deactivate an ambassador"""
    permission_classes = (permissions.IsAuthenticated,)
    queryset = CustomUser.objects.filter(role='ambassador')

    def update(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)
        
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response({
            'message': f'Ambassador {"activated" if user.is_active else "deactivated"}.',
            'user': UserSerializer(user).data
        })


class AdminAmbassadorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Permanently delete an ambassador (admin only)."""
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return CustomUser.objects.none()
        return CustomUser.objects.filter(role='ambassador')

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        label = user.full_name or user.email
        user.delete()
        return Response({'message': f'{label} was deleted.'}, status=status.HTTP_200_OK)


class AdminEventAssignBulkView(generics.CreateAPIView):
    """Assign multiple ambassadors to an event at once"""
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)
        
        event_id = kwargs.get('event_id')
        user_ids = request.data.get('user_ids', [])

        if not user_ids:
            return Response({'error': 'user_ids is required'}, status=400)

        created = 0
        for uid in user_ids:
            _, was_created = UserEventAccess.objects.get_or_create(
                user_id=uid, event_id=event_id,
                defaults={'assigned_by': request.user}
            )
            if was_created:
                created += 1

        return Response({
            'message': f'Assigned {created} ambassador(s) to event.',
            'assigned_count': created
        })

    def delete(self, request, *args, **kwargs):
        """Remove one or more ambassadors from an event without deleting them."""
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        event_id = kwargs.get('event_id')
        user_ids = request.data.get('user_ids') or []
        if not user_ids:
            return Response({'error': 'user_ids is required'}, status=400)

        removed, _ = UserEventAccess.objects.filter(
            event_id=event_id, user_id__in=user_ids
        ).delete()

        return Response({
            'message': f'Unassigned {removed} ambassador(s) from this event.',
            'removed_count': removed
        })


class AdminEventAnalyticsView(generics.RetrieveAPIView):
    """Detailed analytics for a specific event"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)
        
        event_id = kwargs.get('event_id')
        event = Event.objects.get(id=event_id)
        today = timezone.localdate()

        total_guests = Guest.objects.filter(event=event).count()
        checked_in_today = Accreditation.objects.filter(
            event=event, date=today, is_accredited=True
        ).count()
        
        # Per-location breakdown
        by_location = Accreditation.objects.filter(
            event=event, date=today, is_accredited=True
        ).values('location__name').annotate(count=Count('id')).order_by('-count')

        # Per-ambassador breakdown
        by_ambassador = Accreditation.objects.filter(
            event=event, date=today, is_accredited=True
        ).values('verified_by__full_name', 'verified_by__email').annotate(
            count=Count('id')
        ).order_by('-count')

        # Category breakdown
        by_category = Accreditation.objects.filter(
            event=event, date=today, is_accredited=True
        ).values('guest__category__name').annotate(count=Count('id')).order_by('-count')

        return Response({
            'event': EventSerializer(event).data,
            'total_guests': total_guests,
            'checked_in_today': checked_in_today,
            'by_location': list(by_location),
            'by_ambassador': list(by_ambassador),
            'by_category': list(by_category),
        })

# Palette used when an admin CSV import introduces a category the event has
# not configured yet, so imported guests are not silently left uncategorised.
CATEGORY_COLORS = [
    '#2563EB', '#7C3AED', '#DB2777', '#EA580C',
    '#0891B2', '#16A34A', '#CA8A04', '#4F46E5',
]


def ingest_guests(event, guests_data, *, user=None, source='organizer',
                  actor_label='', create_categories=False):
    """
    Shared bulk-guest ingest used by the organizer API and the admin CSV import.

    Deduplicates on email (refreshing the stored name when it changed) and, for
    guests without an email, on the guest name. Row-level failures are collected
    instead of aborting the batch. Returns a plain summary dict.
    """
    created_count = 0
    skipped_count = 0
    errors_list = []
    created_categories = []
    created_ids = []
    duplicates = []

    for idx, raw in enumerate(guests_data):
        g_data = dict(raw) if isinstance(raw, dict) else {}
        # `adult_names` is a deprecated alias kept for existing organizer sheets.
        label = (
            (g_data.get('names') or g_data.get('adult_names') or '').strip()
            or f'Row {idx + 1}'
        )
        try:
            if not isinstance(raw, dict):
                raise ValueError('Guest must be an object')

            # Validate custom_data against the event's schema
            custom_data = g_data.get('custom_data') or {}
            if not isinstance(custom_data, dict):
                raise ValueError('custom_data must be an object')
            if event.custom_fields_schema:
                custom_data = validate_custom_data(custom_data, event.custom_fields_schema)

            # Resolve the category, creating it only for admin imports
            category = None
            category_name = (g_data.get('category_name') or '').strip()
            if category_name:
                category = GuestCategory.objects.filter(
                    event=event,
                    name__iexact=category_name,
                    is_active=True
                ).first()
                if category is None and create_categories:
                    category = GuestCategory.objects.create(
                        event=event,
                        name=category_name[:50],
                        color=CATEGORY_COLORS[
                            len(created_categories) % len(CATEGORY_COLORS)
                        ],
                    )
                    created_categories.append(category.name)

            kids_data = g_data.get('kids') or []
            if not isinstance(kids_data, list):
                raise ValueError('kids must be a list')

            names = (g_data.get('names') or g_data.get('adult_names') or '').strip()
            if not names:
                raise ValueError('A guest name is required')

            email = (g_data.get('email') or '').strip()
            # Phone is capped by the model's max_length; trim noisy input.
            phone = (g_data.get('phone') or '').strip()[:20]

            # A guest is only identifiable and contactable with a name plus at
            # least one way to reach them.
            if not email and not phone:
                raise ValueError('Provide an email address or a phone number')

            # Household details are optional and only sent by the manual form.
            spouse_name = (g_data.get('spouse_name') or '').strip()[:255]
            nanny_name = (g_data.get('nanny_name') or '').strip()[:255]
            allergies = (g_data.get('allergies') or '').strip()
            try:
                nanny_count = max(0, int(g_data.get('nanny_count') or 0))
            except (TypeError, ValueError):
                raise ValueError('nanny_count must be a whole number')

            defaults = {
                'phone': phone,
                'category': category,
                'custom_data': custom_data,
                'spouse_name': spouse_name,
                'nanny_name': nanny_name,
                'nanny_count': nanny_count,
                'allergies': allergies,
            }

            if email:
                # Deduplicate on email, and refresh the name if changed.
                defaults['names'] = names
                guest, created = Guest.objects.get_or_create(
                    event=event,
                    email=email,
                    defaults=defaults
                )
                if not created and names and names != guest.names:
                    guest.names = names
                    guest.save(update_fields=['names'])
            else:
                # No email: deduplicate on the guest's own name so unique
                # attendees without an email are not collapsed into one row.
                guest, created = Guest.objects.get_or_create(
                    event=event,
                    names=names,
                    email='',
                    defaults=defaults
                )

            if created:
                created_count += 1
                created_ids.append(guest.id)
                for k_data in kids_data:
                    if not isinstance(k_data, dict):
                        continue
                    kid_name = (k_data.get('name') or '').strip()
                    if not kid_name:
                        continue
                    try:
                        kid_age = int(k_data.get('age'))
                    except (TypeError, ValueError):
                        continue
                    # The guest is brand new, so each child row is a new kid.
                    Kid.objects.create(
                        guest=guest,
                        name=kid_name[:255],
                        age=kid_age,
                        gender=str(k_data.get('gender') or '')[:50],
                    )

                AuditLog.objects.create(
                    user=user,
                    action={
                        'organizer': 'api_guest_create',
                        'admin_manual': 'admin_guest_create',
                    }.get(source, 'admin_guest_import'),
                    resource_type='Guest',
                    resource_id=guest.id,
                    details={
                        'source': source,
                        **({'organizer': actor_label} if actor_label else {}),
                    }
                )
            else:
                skipped_count += 1
                duplicates.append({'index': idx, 'guest_id': guest.id})
        except Exception as e:
            errors_list.append({
                'index': idx,
                # DRF wraps custom-field problems in a nested detail dict;
                # flatten it so the CSV result reads "Staff_Id is required"
                # instead of Python dict repr.
                'error': (
                    _first_validation_message(e.detail, prefix_fields=False)
                    if isinstance(e, DRFValidationError)
                    else str(e)
                ),
                'guest': label,
            })

    return {
        'created_count': created_count,
        'skipped_count': skipped_count,
        'errors': errors_list,
        'created_categories': created_categories,
        'created_ids': created_ids,
        'duplicates': duplicates,
    }


class OrganizerBulkGuestView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = (OrganizerPermission,)
    serializer_class = OrganizerGuestSerializer

    def create(self, request, *args, **kwargs):
        event = request.organizer_key.event
        guests_data = request.data.get('guests', [])

        if not isinstance(guests_data, list):
            return Response({'error': 'Expected a list of guests'}, status=400)

        if len(guests_data) > 1000:
            return Response(
                {'error': 'Send at most 1000 guests per request. Split your list into smaller batches.'},
                status=400
            )

        result = ingest_guests(
            event,
            guests_data,
            source='organizer',
            actor_label=request.organizer_key.organizer_name,
        )

        return Response({
            'message': f'Processed {len(guests_data)} guests. Created {result["created_count"]} new records.',
            'created_count': result['created_count'],
            'skipped_count': result['skipped_count'],
            'errors': result['errors'] or None
        }, status=201)


class AdminEventBulkGuestView(generics.CreateAPIView):
    """
    Admin guest import used by the dashboard's CSV uploader.

    Accepts the same `{"guests": [...]}` payload as the organizer endpoint but
    authenticates with the admin's JWT. Unlike the organizer path it creates
    missing guest categories, so a list exported from the organizer's sheet
    keeps its ticket types.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = OrganizerGuestSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        event = Event.objects.filter(id=kwargs.get('event_id')).first()
        if not event:
            return Response({'error': 'Event not found.'}, status=404)

        guests_data = request.data.get('guests', [])
        if not isinstance(guests_data, list) or not guests_data:
            return Response(
                {'error': 'Provide a non-empty list of guests.'},
                status=400
            )

        if len(guests_data) > 1000:
            return Response(
                {'error': 'Send at most 1000 guests per request. Split the list into smaller batches.'},
                status=400
            )

        result = ingest_guests(
            event,
            guests_data,
            user=request.user,
            source='admin',
            create_categories=True,
        )

        return Response({
            'message': f'Processed {len(guests_data)} guests. Created {result["created_count"]} new records.',
            'created_count': result['created_count'],
            'skipped_count': result['skipped_count'],
            'created_categories': result['created_categories'],
            'errors': result['errors'] or None,
        }, status=201)


def _first_validation_message(errors, *, prefix_fields=True):
    """Flatten DRF's nested error structure into one readable sentence."""
    if isinstance(errors, dict):
        for field, value in errors.items():
            message = _first_validation_message(
                value, prefix_fields=prefix_fields
            )
            if message:
                if field in ('non_field_errors', 'detail'):
                    return message
                # Nested list errors use integer keys; the field message alone
                # reads better than "0: ...".
                if isinstance(field, int) or not prefix_fields:
                    return message
                return f'{str(field).replace("_", " ").capitalize()}: {message}'
    elif isinstance(errors, (list, tuple)):
        for value in errors:
            message = _first_validation_message(
                value, prefix_fields=prefix_fields
            )
            if message:
                return message
    elif isinstance(errors, str):
        return errors
    return ''


class AdminEventGuestCreateView(generics.CreateAPIView):
    """
    Add one guest by hand from the dashboard.

    Shares the bulk importer's validation and category rules so a manually
    added guest behaves exactly like an imported one, but reports problems
    (and duplicates) as a single readable error for the form.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AdminGuestCreateSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        event = Event.objects.filter(id=kwargs.get('event_id')).first()
        if not event:
            return Response({'error': 'Event not found.'}, status=404)

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': _first_validation_message(serializer.errors)},
                status=400
            )

        data = serializer.validated_data
        result = ingest_guests(
            event,
            [data],
            user=request.user,
            source='admin_manual',
            create_categories=True,
        )

        if result['errors']:
            return Response(
                {'error': result['errors'][0]['error']},
                status=400
            )

        if not result['created_ids']:
            if data.get('email'):
                message = (
                    'A guest with this email address is already on this '
                    'event. Edit that guest instead, or use a different '
                    'email address.'
                )
            else:
                message = (
                    'A guest with this name (and no email) is already on '
                    'this event. Add an email address to tell them apart.'
                )
            payload = {'error': message}
            if result['duplicates']:
                payload['existing_guest_id'] = result['duplicates'][0]['guest_id']
            return Response(payload, status=409)

        guest = (
            Guest.objects
            .select_related('category')
            .prefetch_related('kids')
            .filter(id=result['created_ids'][0])
            .first()
        )
        return Response(
            {
                'message': 'Guest added.',
                **GuestDetailSerializer(guest).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminEventApiKeyListCreateView(generics.ListCreateAPIView):
    """
    Organizer API keys for one event (admin only).

    POST generates a fresh key and returns the raw value exactly once —
    it is never retrievable afterwards, only its SHA-256 digest is stored.
    GET lists keys masked to their prefix.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = OrganizerAPIKeySerializer

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return OrganizerAPIKey.objects.none()
        return OrganizerAPIKey.objects.filter(
            event_id=self.kwargs.get('event_id')
        )

    def create(self, request, *args, **kwargs):
        from .serializers import OrganizerAPIKeyCreateSerializer

        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        event = Event.objects.filter(id=kwargs.get('event_id')).first()
        if not event:
            return Response({'error': 'Event not found.'}, status=404)

        serializer = OrganizerAPIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_key = generate_api_key()
        key_record = OrganizerAPIKey.objects.create(
            event=event,
            organizer_name=serializer.validated_data['organizer_name'],
            key_hash=hash_api_key(raw_key),
            key_prefix=raw_key[:8],
            created_by=request.user,
        )

        AuditLog.objects.create(
            user=request.user,
            action='organizer_api_key_create',
            resource_type='OrganizerAPIKey',
            resource_id=key_record.id,
            details={'event_id': event.id, 'organizer': key_record.organizer_name}
        )

        return Response({
            'message': 'API key created. This is the only time the full key is shown — copy it now.',
            'id': key_record.id,
            'organizer_name': key_record.organizer_name,
            'key_prefix': key_record.key_prefix,
            # Shown once; hashed (never stored in plaintext) afterwards.
            'api_key': raw_key,
        }, status=status.HTTP_201_CREATED)


class AdminEventApiKeyDetailView(generics.DestroyAPIView):
    """Revoke an organizer API key (admin only). The key stops working immediately."""
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if self.request.user.role != 'admin':
            return OrganizerAPIKey.objects.none()
        return OrganizerAPIKey.objects.filter(event_id=self.kwargs.get('event_id'))

    def destroy(self, request, *args, **kwargs):
        key_record = self.get_object()
        key_record.is_active = False
        key_record.save(update_fields=['is_active'])

        AuditLog.objects.create(
            user=request.user,
            action='organizer_api_key_revoke',
            resource_type='OrganizerAPIKey',
            resource_id=key_record.id,
            details={'event_id': key_record.event_id, 'organizer': key_record.organizer_name}
        )

        return Response({'message': 'API key revoked.'}, status=status.HTTP_200_OK)


class EventCustomFieldsView(generics.RetrieveUpdateAPIView):
    """Get or update custom field schema for an event"""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = EventSerializer

    def get_object(self):
        event_id = self.kwargs.get('event_id')
        event = Event.objects.get(id=event_id)
        
        # Check permissions
        if self.request.user.role != 'admin':
            if not UserEventAccess.objects.filter(
                user=self.request.user, event=event
            ).exists():
                raise PermissionDenied("You don't have access to this event")
        
        return event

    def update(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)
        
        event = self.get_object()
        schema = request.data.get('custom_fields_schema', {})
        
        # Validate schema structure
        if 'fields' in schema:
            for field in schema['fields']:
                if not all(k in field for k in ['key', 'label', 'type']):
                    return Response({
                        'error': 'Each field must have key, label, and type'
                    }, status=400)
        
        event.custom_fields_schema = schema
        event.save(update_fields=['custom_fields_schema'])
        
        return Response({
            'message': 'Custom fields schema updated',
            'schema': event.custom_fields_schema
        })


# ==========================================
# Reporting
# ==========================================

MAX_REPORT_DAYS = 62


def _daily_series(event, daily_rows):
    """Every scheduled day of the event, filled with zeros where needed."""
    totals = {row['date']: row for row in daily_rows}
    series = []
    cursor = event.start_date
    end = event.end_date

    if not cursor or not end or cursor > end:
        return series

    while cursor <= end and len(series) < MAX_REPORT_DAYS:
        row = totals.get(cursor)
        series.append({
            'date': cursor.isoformat(),
            'checkins': row['checkins'] if row else 0,
            'guests': row['guests'] if row else 0,
        })
        cursor += timedelta(days=1)

    return series


def _event_summary(event):
    """Cheap report aggregates (no guest list) for an event."""
    today = timezone.localdate()
    accreditations = Accreditation.objects.filter(event=event, is_accredited=True)

    total_guests = Guest.objects.filter(event=event).count()
    accredited_guests = accreditations.values('guest_id').distinct().count()
    total_checkins = accreditations.count()
    checked_in_today = accreditations.filter(date=today).count()

    daily_rows = list(
        accreditations.values('date')
        .annotate(checkins=Count('id'), guests=Count('guest', distinct=True))
        .order_by('date')
    )
    first = accreditations.order_by('date', 'time').values('date', 'time').first()
    last = accreditations.order_by('-date', '-time').values('date', 'time').first()

    attendance_rate = (
        round((accredited_guests / total_guests) * 100, 1) if total_guests else 0.0
    )

    return {
        'total_guests': total_guests,
        'accredited_guests': accredited_guests,
        'total_checkins': total_checkins,
        'checked_in_today': checked_in_today,
        'attendance_rate': attendance_rate,
        'no_shows': max(0, total_guests - accredited_guests),
        'locations': event.locations.filter(is_active=True).count(),
        'categories': event.categories.filter(is_active=True).count(),
        'ambassadors': UserEventAccess.objects.filter(
            event=event, user__is_active=True
        ).count(),
        'first_checkin_date': (
            first['date'].isoformat() if first and first.get('date') else None
        ),
        'last_checkin_at': (
            datetime.combine(last['date'], last['time'] or time.min).isoformat()
            if last and last.get('date')
            else None
        ),
        'avg_checkins_per_day': (
            round(total_checkins / len(daily_rows), 1) if daily_rows else 0.0
        ),
        'daily': _daily_series(event, daily_rows),
    }


def _hour_range(event, observed_hours=None):
    """Chart window: the event's daily schedule plus any hour with data."""
    starts = []
    ends = []

    for window in (event.daily_schedule or {}).values():
        if not isinstance(window, dict):
            continue
        for key, bucket in (('start', starts), ('end', ends)):
            value = str(window.get(key) or '')
            if ':' not in value:
                continue
            try:
                bucket.append(int(value.split(':')[0]))
            except (TypeError, ValueError):
                continue

    observed = [hour for hour in (observed_hours or []) if 0 <= hour <= 23]
    start_hour = min(starts + observed) if (starts or observed) else 8
    end_hour = max([end - 1 for end in ends] + observed) if (ends or observed) else 19

    start_hour = max(0, start_hour)
    end_hour = min(23, end_hour)

    if end_hour < start_hour:
        return 0, 23

    return start_hour, end_hour


def _event_report(event):
    """Full report payload for a single event, including the guest list."""
    accreditations = Accreditation.objects.filter(event=event, is_accredited=True)
    summary = _event_summary(event)
    total_checkins = summary['total_checkins']

    hourly_counts = {}
    for checked_at in accreditations.values_list('time', flat=True):
        hour = checked_at.hour if checked_at else 0
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

    start_hour, end_hour = _hour_range(event, hourly_counts.keys())
    hourly = [
        {'hour': f'{hour:02d}:00', 'count': hourly_counts.get(hour, 0)}
        for hour in range(start_hour, end_hour + 1)
    ]

    guest_counts = {
        row['category_id']: row['count']
        for row in Guest.objects.filter(event=event)
        .values('category_id')
        .annotate(count=Count('id'))
    }
    checked_by_category = {
        row['guest__category_id']: row
        for row in accreditations.values('guest__category_id').annotate(
            checkins=Count('id'), guests=Count('guest', distinct=True)
        )
    }

    by_category = []
    for category in event.categories.all():
        guests = guest_counts.get(category.id, 0)
        checked = checked_by_category.get(category.id, {})
        checked_guests = checked.get('guests', 0)
        by_category.append({
            'id': category.id,
            'name': category.name,
            'color': category.color,
            'guests': guests,
            'checked_in': checked_guests,
            'checkins': checked.get('checkins', 0),
            'rate': round((checked_guests / guests) * 100, 1) if guests else 0.0,
        })

    uncategorized_guests = guest_counts.get(None, 0)
    if uncategorized_guests:
        checked = checked_by_category.get(None, {})
        checked_guests = checked.get('guests', 0)
        by_category.append({
            'id': None,
            'name': 'Uncategorized',
            'color': '#94A3B8',
            'guests': uncategorized_guests,
            'checked_in': checked_guests,
            'checkins': checked.get('checkins', 0),
            'rate': (
                round((checked_guests / uncategorized_guests) * 100, 1)
                if uncategorized_guests
                else 0.0
            ),
        })

    by_location = [
        {
            'name': row['location__name'] or 'No location',
            'count': row['count'],
            'share': (
                round((row['count'] / total_checkins) * 100, 1)
                if total_checkins
                else 0.0
            ),
        }
        for row in accreditations.values('location__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    ]

    by_ambassador = [
        {
            'name': row['verified_by__full_name'] or 'Unassigned',
            'email': row['verified_by__email'] or '',
            'count': row['count'],
        }
        for row in accreditations.values(
            'verified_by__full_name', 'verified_by__email'
        )
        .annotate(count=Count('id'))
        .order_by('-count')
    ]

    first_checkin = {}
    last_checkin = {}
    for row in accreditations.order_by(
        'guest_id', 'date', 'time'
    ).values('guest_id', 'date', 'time', 'location__name'):
        first_checkin.setdefault(row['guest_id'], row)
        last_checkin[row['guest_id']] = row

    guest_queryset = (
        Guest.objects.filter(event=event)
        .select_related('category')
        .prefetch_related('kids')
        .annotate(
            checkin_count=Count(
                'accreditations', filter=Q(accreditations__is_accredited=True)
            )
        )
        .order_by('names')
    )

    guests = []
    for guest in guest_queryset:
        first = first_checkin.get(guest.id)
        last = last_checkin.get(guest.id)
        guests.append({
            'id': guest.id,
            'ticket_number': guest.ticket_number,
            'names': guest.names,
            # Deprecated alias kept for dashboard builds deployed before the
            # rename; safe to drop once every client reads `names`.
            'adult_names': guest.names,
            'email': guest.email,
            'phone': guest.phone,
            'category': guest.category.name if guest.category else None,
            'category_color': guest.category.color if guest.category else None,
            'kids_count': len(guest.kids.all()),
            'custom_data': guest.custom_data or {},
            'checked_in': guest.checkin_count > 0,
            'checkins': guest.checkin_count,
            'first_checkin_date': (
                first['date'].isoformat() if first and first.get('date') else None
            ),
            'last_checkin_date': (
                last['date'].isoformat() if last and last.get('date') else None
            ),
            'last_checkin_time': (
                last['time'].isoformat()
                if last and last.get('time')
                else None
            ),
            'location': last['location__name'] if last else None,
        })

    recent_checkins = [
        {
            'guest_name': row.guest.names,
            'category': row.guest.category.name if row.guest.category else None,
            'location': row.location.name if row.location else None,
            'ambassador': row.verified_by.full_name if row.verified_by else None,
            'date': row.date.isoformat(),
            'time': row.time.isoformat() if row.time else None,
        }
        for row in accreditations.select_related(
            'guest__category', 'location', 'verified_by'
        ).order_by('-date', '-time')[:12]
    ]

    summary_payload = {key: value for key, value in summary.items() if key != 'daily'}

    return {
        'event': EventSerializer(event).data,
        'generated_at': timezone.now().isoformat(),
        'summary': summary_payload,
        'daily': summary['daily'],
        'hourly': hourly,
        'by_category': by_category,
        'by_location': by_location,
        'by_ambassador': by_ambassador,
        'recent_checkins': recent_checkins,
        'guests': guests,
        'custom_fields': (event.custom_fields_schema or {}).get('fields', []),
    }


class AdminReportsListView(APIView):
    """Summary of every event, used by the reports index page."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        events = Event.objects.select_related('created_by').prefetch_related(
            'locations', 'categories'
        ).order_by('-start_date')

        reports = []
        totals = {
            'events': 0,
            'total_guests': 0,
            'accredited_guests': 0,
            'total_checkins': 0,
            'checked_in_today': 0,
            'attendance_rate': 0.0,
        }

        for event in events:
            summary = _event_summary(event)
            reports.append({
                'event': EventSerializer(event).data,
                **summary,
            })
            for key in (
                'total_guests',
                'accredited_guests',
                'total_checkins',
                'checked_in_today',
            ):
                totals[key] += summary[key]

        totals['events'] = len(reports)
        totals['attendance_rate'] = (
            round((totals['accredited_guests'] / totals['total_guests']) * 100, 1)
            if totals['total_guests']
            else 0.0
        )

        return Response({'reports': reports, 'totals': totals})


class AdminEventReportView(APIView):
    """Detailed report for a single event."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, event_id, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        try:
            event = Event.objects.select_related('created_by').prefetch_related(
                'locations', 'categories'
            ).get(pk=event_id)
        except Event.DoesNotExist:
            return Response({'error': 'Event not found'}, status=404)

        return Response(_event_report(event))