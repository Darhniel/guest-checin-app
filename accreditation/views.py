from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from .models import CustomUser, Event, Location, GuestCategory, UserEventAccess
from .serializers import (
    UserSerializer, UserCreateSerializer, EventSerializer, 
    LocationSerializer, GuestCategorySerializer, OrganizerGuestSerializer
)
from django.utils import timezone
from django.db.models import Q, Count
from django.db.models.functions import TruncHour
from rest_framework.permissions import AllowAny
from .models import Guest, Kid, Accreditation, OrganizerAPIKey, AuditLog
from .serializers import GuestSummarySerializer, GuestDetailSerializer, AccreditationSerializer, OrganizerAPIKeySerializer
import logging
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
        return Guest.objects.filter(event_id=event_id).order_by('adult_names')
    
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
        return GuestCategory.objects.filter(event_id=event_id).order_by('-priority')

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
            Q(adult_names__iexact=identifier) | Q(ticket_number__iexact=identifier),
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
            adult_names__icontains=query
        ).order_by('adult_names')[:10]

        # Annotate with checked-in status for the UI
        for guest in guests:
            guest.is_checked_in_today = guest.id in accredited_ids
            
        return guests

# ==========================================
# ORGANIZER API VIEWS
# ==========================================

class OrganizerPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        api_key = request.headers.get('Authorization')
        if not api_key or not api_key.startswith('Bearer '):
            return False
        
        key_value = api_key.split(' ')[1]
        try:
            request.organizer_key = OrganizerAPIKey.objects.select_related('event').get(key=key_value, is_active=True)
            # Update last used
            request.organizer_key.last_used = timezone.now()
            request.organizer_key.save(update_fields=['last_used'])
            return True
        except OrganizerAPIKey.DoesNotExist:
            return False

class OrganizerBulkGuestView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = (OrganizerPermission,)
    
    def create(self, request, *args, **kwargs):
        event = request.organizer_key.event
        guests_data = request.data.get('guests', [])
        
        if not isinstance(guests_data, list):
            return Response({'error': 'Expected a list of guests'}, status=400)

        created_count = 0
        for g_data in guests_data:
            # Basic validation
            if not g_data.get('adult_names') or not g_data.get('email'):
                continue
                
            kids_data = g_data.pop('kids', [])
            
            guest, created = Guest.objects.get_or_create(
                event=event,
                email=g_data.get('email'),
                defaults={**g_data, 'event': event}
            )
            
            if created:
                created_count += 1
                # Create kids if provided
                for k_data in kids_data:
                    Kid.objects.get_or_create(guest=guest, defaults=k_data)
                    
                AuditLog.objects.create(
                    action='api_guest_create',
                    resource_type='Guest',
                    resource_id=guest.id,
                    details={'organizer': request.organizer_key.organizer_name}
                )

        return Response({
            'message': f'Successfully processed {len(guests_data)} guests. Created {created_count} new records.',
            'created_count': created_count
        }, status=201)

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

class OrganizerBulkGuestView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = (OrganizerPermission,)
    serializer_class = OrganizerGuestSerializer

    def create(self, request, *args, **kwargs):
        event = request.organizer_key.event
        guests_data = request.data.get('guests', [])
        
        if not isinstance(guests_data, list):
            return Response({'error': 'Expected a list of guests'}, status=400)

        created_count = 0
        errors_list = []
        
        for idx, g_data in enumerate(guests_data):
            try:
                # Validate custom_data against event schema
                custom_data = g_data.get('custom_data', {})
                if event.custom_fields_schema:
                    custom_data = validate_custom_data(custom_data, event.custom_fields_schema)
                
                # Find or create category
                category = None
                category_name = g_data.get('category_name')
                if category_name:
                    category = GuestCategory.objects.filter(
                        event=event,
                        name__iexact=category_name
                    ).first()
                
                # Create guest
                kids_data = g_data.pop('kids', [])
                
                guest, created = Guest.objects.get_or_create(
                    event=event,
                    email=g_data.get('email', ''),
                    defaults={
                        'adult_names': g_data['adult_names'],
                        'phone': g_data.get('phone', ''),
                        'category': category,
                        'custom_data': custom_data,
                    }
                )
                
                if created:
                    created_count += 1
                    for k_data in kids_data:
                        Kid.objects.get_or_create(guest=guest, defaults=k_data)
                        
                    AuditLog.objects.create(
                        action='api_guest_create',
                        resource_type='Guest',
                        resource_id=guest.id,
                        details={'organizer': request.organizer_key.organizer_name}
                    )
            except Exception as e:
                errors_list.append({
                    'index': idx,
                    'error': str(e),
                    'guest': g_data.get('adult_names', 'Unknown')
                })

        return Response({
            'message': f'Processed {len(guests_data)} guests. Created {created_count} new records.',
            'created_count': created_count,
            'errors': errors_list if errors_list else None
        }, status=201)
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