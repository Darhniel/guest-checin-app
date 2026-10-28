from django.db import transaction
from django.views import generic
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Accreditation, Event, Guest, Kid, Location, GuestCategory, OrganizerAPIKey, UserEventAccess

User = get_user_model()

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
        fields = ('id', 'email', 'full_name', 'phone', 'role', 'first_login', 'is_active')
        read_only_fields = ('id', 'first_login')

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

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'logo', 'location_text', 
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

class KidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kid
        fields = ('id', 'name', 'age', 'gender')

# 🛡️ PRIVACY RULE: Ambassadors only see this
class GuestSummarySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    kids_count = serializers.SerializerMethodField()
    is_checked_in_today = serializers.SerializerMethodField()
    # Deprecated read-only alias so already-installed mobile clients keep
    # working while they move from `adult_names` to `names`.
    adult_names = serializers.CharField(source='names', read_only=True)

    class Meta:
        model = Guest
        fields = ('id', 'names', 'adult_names', 'category_name', 'category_color', 'kids_count', 'is_checked_in_today', 'ticket_number')

    def get_kids_count(self, obj):  # ✅ FIXED: Use method instead of source
        return obj.kids.count()
    
    def get_is_checked_in_today(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        return obj.accreditations.filter(date=today, is_accredited=True).exists()

# 🛡️ PRIVACY RULE: Admins see this
class GuestDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    kids = KidSerializer(many=True, read_only=True)
    is_checked_in_today = serializers.SerializerMethodField()
    # Deprecated read-only alias, see GuestSummarySerializer.
    adult_names = serializers.CharField(source='names', read_only=True)

    class Meta:
        model = Guest
        fields = ('id', 'names', 'adult_names', 'spouse_name', 'email', 'phone', 'nanny_name', 'nanny_count', 'allergies', 'category_name', 'kids', 'ticket_number', 'custom_data', 'is_checked_in_today')

    def get_is_checked_in_today(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        return obj.accreditations.filter(date=today, is_accredited=True).exists()

class AccreditationSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='guest.names', read_only=True)
    category_name = serializers.CharField(source='guest.category.name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True, allow_null=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    kids_count = serializers.SerializerMethodField()

    class Meta:
        model = Accreditation
        fields = ('id', 'guest_name', 'category_name', 'verified_by_name', 'location_name', 'date', 'time', 'is_accredited', 'kids_count')

    def get_kids_count(self, obj):  # ✅ FIXED
        return obj.guest.kids.count() if obj.guest else 0

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

    A row is valid only with a name plus an email or a phone number.
    `adult_names` is still accepted as a deprecated input alias so existing
    organizer scripts and spreadsheets keep working.
    """
    names = serializers.CharField(required=False, allow_blank=True)
    adult_names = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    category_name = serializers.CharField(required=False, allow_blank=True)
    custom_data = serializers.DictField(required=False, default=dict)
    kids = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    def validate(self, attrs):
        names = (attrs.get('names') or attrs.get('adult_names') or '').strip()
        if not names:
            raise serializers.ValidationError(
                {'names': 'At least one guest name is required.'}
            )

        if not (attrs.get('email') or '').strip() and not (attrs.get('phone') or '').strip():
            raise serializers.ValidationError(
                {'email': 'Provide an email address or a phone number.'}
            )

        attrs['names'] = names
        return attrs

class AdminGuestKidSerializer(serializers.Serializer):
    """One child submitted alongside a manually entered guest."""

    name = serializers.CharField(max_length=255)
    age = serializers.IntegerField(min_value=0, max_value=120)
    gender = serializers.CharField(required=False, allow_blank=True, max_length=50)

class AdminGuestCreateSerializer(serializers.Serializer):
    """
    One guest submitted from the dashboard's manual entry form.

    Mirrors the bulk-ingest rules (a name plus an email or a phone number) but
    validates eagerly so the form can show a field-specific message instead of
    a row-level import error.
    """

    names = serializers.CharField(allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    category_name = serializers.CharField(required=False, allow_blank=True, max_length=50)
    spouse_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    nanny_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    nanny_count = serializers.IntegerField(required=False, min_value=0, default=0)
    allergies = serializers.CharField(required=False, allow_blank=True)
    custom_data = serializers.DictField(required=False, default=dict)
    kids = AdminGuestKidSerializer(many=True, required=False, default=list)

    def validate_names(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                'At least one guest name is required.'
            )
        return value

    def validate(self, attrs):
        email = (attrs.get('email') or '').strip()
        phone = (attrs.get('phone') or '').strip()

        if not email and not phone:
            raise serializers.ValidationError(
                {'email': 'Provide an email address or a phone number.'}
            )

        attrs['email'] = email
        attrs['phone'] = phone
        return attrs