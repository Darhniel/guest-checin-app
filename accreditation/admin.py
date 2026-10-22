from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Accreditation, CustomUser, Event, Guest, Kid, Location, GuestCategory, OrganizerAPIKey, UserEventAccess



@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # 1. Fix the ordering error
    ordering = ('email',)
    
    # 2. Fix search fields (default includes 'username')
    search_fields = ('email', 'full_name')
    
    list_display = ('email', 'full_name', 'role', 'first_login', 'is_active')
    list_filter = ('role', 'is_active', 'first_login')
    
    # 3. Redefine fieldsets completely. 
    # (You cannot just append to UserAdmin.fieldsets because it contains 'username')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Extra Info', {'fields': ('role', 'first_login')}),
    )
    
    # 4. Your add_fieldsets was mostly correct, just formatted cleanly here
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'phone', 'password1', 'password2', 'role'),
        }),
    )

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active', 'created_by')
    list_filter = ('is_active', 'start_date')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'is_active', 'order')
    list_filter = ('event', 'is_active')

@admin.register(GuestCategory)
class GuestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'color', 'priority')

@admin.register(UserEventAccess)
class UserEventAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'assigned_at', 'assigned_by')

@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('adult_names', 'event', 'category', 'ticket_number', 'email')
    list_filter = ('event', 'category')
    search_fields = ('adult_names', 'ticket_number', 'email')

@admin.register(Kid)
class KidAdmin(admin.ModelAdmin):
    list_display = ('name', 'age', 'guest')
    search_fields = ('name', 'guest__adult_names')

@admin.register(Accreditation)
class AccreditationAdmin(admin.ModelAdmin):
    list_display = ('guest', 'event', 'verified_by', 'location', 'date', 'time')
    list_filter = ('event', 'date', 'location')
    search_fields = ('guest__adult_names', 'verified_by__full_name')

@admin.register(OrganizerAPIKey)
class OrganizerAPIKeyAdmin(admin.ModelAdmin):
    # Full keys are never displayed anywhere: they are hashed at rest.
    list_display = ('organizer_name', 'event', 'key_prefix', 'is_active', 'last_used')
    list_filter = ('event', 'is_active')