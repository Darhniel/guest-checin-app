from rest_framework import serializers
from .models import Guest, Kid, Accreditation

class KidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kid
        fields = ['name', 'age', 'gender']

class GuestDetailSerializer(serializers.ModelSerializer):
    kids = KidSerializer(many=True, read_only=True)

    class Meta:
        model = Guest
        fields = ['adult_names', 'spouse_name', 'nanny_name', 'email', 'phone', 'kids']

class AccreditationSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='guest.adult_names', read_only=True)
    kids_count = serializers.SerializerMethodField()
    id = serializers.CharField(source='guest.adult_names', read_only=True)
    ok = serializers.BooleanField(source='is_accredited', read_only=True)
    kids_count = serializers.SerializerMethodField()

    class Meta:
        model = Accreditation
        fields = ['id', 'ok', 'date', 'time', 'is_accredited', 'kids_count']

    def get_kids_count(self, obj):
        return obj.guest.kids.count() if obj.guest else 0