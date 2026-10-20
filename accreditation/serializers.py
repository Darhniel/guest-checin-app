from django.views import generic
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Accreditation, Event, Guest, Kid, Location, GuestCategory, OrganizerAPIKey, UserEventAccess

User = get_user_model()

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
    class Meta:
        model = Location
        fields = ('id', 'name', 'description', 'is_active', 'order')

class GuestCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestCategory
        fields = ('id', 'name', 'color', 'priority')

class EventSerializer(serializers.ModelSerializer):
    locations = LocationSerializer(many=True, read_only=True)
    categories = GuestCategorySerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    ambassadors = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'logo', 'location_text', 
            'start_date', 'end_date', 'daily_schedule', 'enforce_hours', 'is_active', 
            'created_by', 'created_at', 'locations', 'categories', 'ambassadors'
        )

    def get_ambassadors(self, obj):
        # Fetch all access records for this event and grab the associated user
        # ⚠️ IMPORTANT: If your ForeignKey in UserEventAccess is named 'ambassador' 
        # instead of 'user', change 'access.user' to 'access.ambassador' below.
        accesses = UserEventAccess.objects.filter(event=obj).select_related('user')
        
        # Serialize and return the list of users
        return UserSerializer([access.user for access in accesses], many=True).data

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

    class Meta:
        model = Guest
        fields = ('id', 'adult_names', 'category_name', 'category_color', 'kids_count', 'is_checked_in_today', 'ticket_number')

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

    class Meta:
        model = Guest
        fields = ('id', 'adult_names', 'spouse_name', 'email', 'phone', 'nanny_name', 'nanny_count', 'allergies', 'category_name', 'kids', 'ticket_number', 'custom_data', 'is_checked_in_today')

    def get_is_checked_in_today(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        return obj.accreditations.filter(date=today, is_accredited=True).exists()

class AccreditationSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='guest.adult_names', read_only=True)
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
    class Meta:
        model = OrganizerAPIKey
        fields = ('id', 'key', 'organizer_name', 'is_active', 'created_at', 'last_used')
        read_only_fields = ('key',)

class OrganizerGuestSerializer(serializers.Serializer):
    adult_names = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    category_name = serializers.CharField(required=False, allow_blank=True)
    custom_data = serializers.DictField(required=False, default=dict)
    kids = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )