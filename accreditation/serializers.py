import base64
import binascii
from django.db import transaction
from django.views import generic
from django.core.files.base import ContentFile
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Accreditation,
    Event,
    Guest,
    Location,
    GuestCategory,
    OrganizerAPIKey,
    UserEventAccess,
    split_guest_name,
)

User = get_user_model()

# Event flyers are sent from the dashboard as base64 data URLs inside the JSON
# event payload. Keep the same 5 MB ceiling the upload UI advertises.
FLYER_MAX_BYTES = 5 * 1024 * 1024
FLYER_MIME_EXTENSIONS = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/webp': '.webp',
    'image/gif': '.gif',
}


class Base64ImageField(serializers.ImageField):
    """ImageField that also accepts a ``data:<mime>;base64,<payload>`` string.

    The dashboard keeps the whole event (including nested locations and
    categories) in one JSON request, so the flyer cannot be a multipart part.
    Decoding the data URL here keeps that single-request flow while still
    storing a real image file on the model.
    """

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:'):
            try:
                header, payload = data.split(',', 1)
                metadata = header[5:]
            except ValueError:
                raise serializers.ValidationError('Invalid flyer data.')

            mime_type = metadata.split(';', 1)[0].strip().lower()
            if ';base64' not in metadata.lower():
                raise serializers.ValidationError(
                    'Flyer must be base64-encoded.'
                )
            if mime_type not in FLYER_MIME_EXTENSIONS:
                raise serializers.ValidationError(
                    'Upload a PNG, JPG, WebP, or GIF image.'
                )

            try:
                decoded = base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError):
                raise serializers.ValidationError('Invalid flyer data.')

            if len(decoded) > FLYER_MAX_BYTES:
                raise serializers.ValidationError(
                    'Flyer must be 5 MB or smaller.'
                )

            data = ContentFile(
                decoded,
                name=f'flyer{FLYER_MIME_EXTENSIONS[mime_type]}',
            )

        return super().to_internal_value(data)

class ActiveListSerializer(serializers.ListSerializer):
    """Only expose active rows while still supporting nested writes."""

    def to_representation(self, data):
        iterable = data.all() if hasattr(data, 'all') else data
        return super().to_representation(
            [item for item in iterable if getattr(item, 'is_active', True)]
        )

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'phone', 'role', 'first_login', 'is_active', 'date_joined')
        read_only_fields = ('id', 'first_login', 'date_joined')

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    full_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone', 'password', 'role')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            phone=validated_data.get('phone', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'ambassador'),
            first_login=True
        )
        return user

class AdminCreateSerializer(serializers.ModelSerializer):
    """Create an admin or a view-only supervisor.

    The role is intentionally limited so this endpoint can never be used to
    mint ambassadors (or anything else) by accident.
    """

    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    full_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(
        choices=(User.ROLE_ADMIN, User.ROLE_SUPERVISOR),
        default=User.ROLE_SUPERVISOR,
    )

    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone', 'password', 'role')

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            phone=validated_data.get('phone', ''),
            password=validated_data['password'],
            role=validated_data.get('role', User.ROLE_SUPERVISOR),
            first_login=True,
        )

class LocationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Location
        fields = ('id', 'name', 'description', 'is_active', 'order')
        list_serializer_class = ActiveListSerializer

class GuestCategorySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = GuestCategory
        fields = ('id', 'name', 'color', 'priority', 'is_active')
        read_only_fields = ('is_active',)
        list_serializer_class = ActiveListSerializer

class EventSerializer(serializers.ModelSerializer):
    locations = LocationSerializer(many=True, required=False)
    categories = GuestCategorySerializer(many=True, required=False)
    created_by = UserSerializer(read_only=True)
    ambassadors = serializers.SerializerMethodField()
    flyer = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'logo', 'flyer', 'location_text', 
            'start_date', 'end_date', 'daily_schedule', 'custom_fields_schema',
            'enforce_hours', 'is_active',
            'created_by', 'created_at', 'locations', 'categories', 'ambassadors'
        )

    def get_ambassadors(self, obj):
        # Fetch all access records for this event and grab the associated user
        # ⚠️ IMPORTANT: If your ForeignKey in UserEventAccess is named 'ambassador' 
        # instead of 'user', change 'access.user' to 'access.ambassador' below.
        accesses = UserEventAccess.objects.filter(event=obj).select_related('user')
        
        # Serialize and return the list of users
        return UserSerializer([access.user for access in accesses], many=True).data

    @staticmethod
    def _sync_locations(event, locations_data):
        existing = {location.id: location for location in event.locations.all()}
        kept_ids = []

        for index, location_data in enumerate(locations_data):
            data = dict(location_data)
            location_id = data.pop('id', None)
            data.pop('is_active', None)
            data['order'] = data.get('order', index)

            location = existing.get(location_id) if location_id else None
            if location is None:
                location = Location.objects.create(event=event, **data)
            else:
                for attribute, value in data.items():
                    setattr(location, attribute, value)
                location.is_active = True
                location.save()

            kept_ids.append(location.id)

        # Keep historical references intact but hide removed points from the UI.
        event.locations.exclude(id__in=kept_ids).update(is_active=False)

    @staticmethod
    def _sync_categories(event, categories_data):
        existing = {category.id: category for category in event.categories.all()}
        kept_ids = []

        for category_data in categories_data:
            data = dict(category_data)
            category_id = data.pop('id', None)
            data.pop('is_active', None)

            category = existing.get(category_id) if category_id else None
            if category is None:
                category = GuestCategory.objects.create(event=event, **data)
            else:
                for attribute, value in data.items():
                    setattr(category, attribute, value)
                category.is_active = True
                category.save()

            kept_ids.append(category.id)

        # Past guests keep their category, but it is no longer offered for new guests.
        event.categories.exclude(id__in=kept_ids).update(is_active=False)

    @transaction.atomic
    def create(self, validated_data):
        locations_data = validated_data.pop('locations', [])
        categories_data = validated_data.pop('categories', [])
        event = Event.objects.create(**validated_data)

        self._sync_locations(event, locations_data)
        self._sync_categories(event, categories_data)
        return event

    @transaction.atomic
    def update(self, instance, validated_data):
        locations_data = validated_data.pop('locations', None)
        categories_data = validated_data.pop('categories', None)

        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()

        if locations_data is not None:
            self._sync_locations(instance, locations_data)
        if categories_data is not None:
            self._sync_categories(instance, categories_data)

        return instance

# 🛡️ PRIVACY RULE: Ambassadors only see this
class GuestSummarySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    is_checked_in_today = serializers.SerializerMethodField()
    # Full name is derived from first_name/last_name but still emitted as
    # `names` so installed mobile clients and the dashboard keep working.
    names = serializers.CharField(read_only=True)
    adult_names = serializers.CharField(source='names', read_only=True)

    class Meta:
        model = Guest
        fields = ('id', 'names', 'first_name', 'last_name', 'adult_names', 'category_name', 'category_color', 'is_checked_in_today', 'ticket_number')

    def get_is_checked_in_today(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        return obj.accreditations.filter(date=today, is_accredited=True).exists()

# 🛡️ PRIVACY RULE: Admins see this
class GuestDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_checked_in_today = serializers.SerializerMethodField()
    names = serializers.CharField(read_only=True)
    adult_names = serializers.CharField(source='names', read_only=True)
    # `phone` is kept as a read-only alias for clients built before the
    # phone_number rename.
    phone = serializers.CharField(source='phone_number', read_only=True)

    class Meta:
        model = Guest
        fields = ('id', 'names', 'first_name', 'last_name', 'adult_names', 'email', 'phone', 'phone_number', 'category_name', 'ticket_number', 'custom_data', 'is_checked_in_today')

    def get_is_checked_in_today(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        return obj.accreditations.filter(date=today, is_accredited=True).exists()

class AccreditationSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='guest.names', read_only=True)
    category_name = serializers.CharField(source='guest.category.name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True, allow_null=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)

    class Meta:
        model = Accreditation
        fields = ('id', 'guest_name', 'category_name', 'verified_by_name', 'location_name', 'date', 'time', 'is_accredited')

class OrganizerAPIKeySerializer(serializers.ModelSerializer):
    """Masked representation — the raw key is never returned here."""

    class Meta:
        model = OrganizerAPIKey
        fields = ('id', 'organizer_name', 'key_prefix', 'is_active', 'created_at', 'last_used')
        read_only_fields = fields

class OrganizerAPIKeyCreateSerializer(serializers.Serializer):
    organizer_name = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_organizer_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Organizer name is required.')
        return value

class OrganizerGuestSerializer(serializers.Serializer):
    """
    One guest row accepted by the bulk-ingest endpoints.

    `first_name` and `last_name` are required; email and phone are optional.
    `names` / `adult_names` remain accepted as deprecated single-field aliases
    for older organizer sheets and are split into a first and last name.
    """
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    names = serializers.CharField(required=False, allow_blank=True, write_only=True)
    adult_names = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    category_name = serializers.CharField(required=False, allow_blank=True)
    custom_data = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        first_name = (attrs.get('first_name') or '').strip()
        last_name = (attrs.get('last_name') or '').strip()
        legacy_name = (attrs.get('names') or attrs.get('adult_names') or '').strip()

        if not first_name and not last_name and legacy_name:
            first_name, last_name = split_guest_name(legacy_name)

        errors = {}
        if not first_name:
            errors['first_name'] = 'A first name is required.'
        # A legacy single-field name may be a mononym such as "Prince"; new
        # payloads must send both name columns.
        if not last_name and not legacy_name:
            errors['last_name'] = 'A last name is required.'
        if errors:
            raise serializers.ValidationError(errors)

        attrs['first_name'] = first_name
        attrs['last_name'] = last_name
        attrs['phone_number'] = (
            attrs.get('phone_number') or attrs.get('phone') or ''
        ).strip()
        attrs.pop('names', None)
        attrs.pop('adult_names', None)
        return attrs

class AdminGuestCreateSerializer(serializers.Serializer):
    """
    One guest submitted from the dashboard's manual entry form.

    First and last name are required; email and phone number are optional.
    The dashboard still submits a single `names` field, which is split into
    the two columns for backward compatibility.
    """

    first_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    names = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    category_name = serializers.CharField(required=False, allow_blank=True, max_length=50)
    custom_data = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        first_name = (attrs.get('first_name') or '').strip()
        last_name = (attrs.get('last_name') or '').strip()
        legacy_name = (attrs.get('names') or '').strip()

        if not first_name and not last_name and legacy_name:
            first_name, last_name = split_guest_name(legacy_name)

        errors = {}
        if not first_name:
            errors['first_name'] = 'A first name is required.'
        # A legacy single-field name such as "Prince" is accepted as-is; the
        # split just leaves the last name empty.
        if not last_name and not legacy_name:
            errors['last_name'] = 'A last name is required.'
        if errors:
            raise serializers.ValidationError(errors)

        attrs['first_name'] = first_name
        attrs['last_name'] = last_name
        attrs['email'] = (attrs.get('email') or '').strip()
        attrs['phone_number'] = (
            attrs.get('phone_number') or attrs.get('phone') or ''
        ).strip()[:20]
        return attrs