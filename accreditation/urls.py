from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path('auth/login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Admin: Ambassador Management
    path('admin/ambassadors/', views.AmbassadorCreateView.as_view(), name='ambassador_create'),
    path('admin/events/<int:event_id>/assign/', views.AssignAmbassadorView.as_view(), name='assign_ambassador'),

    # Events
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    
    # Event-specific resources
    path('events/<int:event_id>/locations/', views.LocationListView.as_view(), name='location_list'),
    path('events/<int:event_id>/categories/', views.CategoryListView.as_view(), name='category_list'),
    path('events/<int:event_id>/guests/', views.EventGuestsListView.as_view(), name='event_guests'),

    # Check-in & Activity (Ambassador)
    path('events/<int:event_id>/check-in/', views.CheckInView.as_view(), name='check_in'),
    path('events/<int:event_id>/activity-log/', views.ActivityLogView.as_view(), name='activity_log'),
    path('events/<int:event_id>/search-guests/', views.SearchGuestsView.as_view(), name='search_guests'),

    # Organizer API
    path('organizers/events/<int:event_id>/guests/bulk/', views.OrganizerBulkGuestView.as_view(), name='organizer_bulk_guests'),

    # Admin Dashboard
    path('admin/dashboard/stats/', views.AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('admin/ambassadors/list/', views.AdminAmbassadorListView.as_view(), name='admin_ambassador_list'),
    path('admin/ambassadors/<int:pk>/', views.AdminAmbassadorDetailView.as_view(), name='admin_ambassador_detail'),
    path('admin/ambassadors/<int:pk>/toggle/', views.AdminAmbassadorToggleView.as_view(), name='admin_ambassador_toggle'),
    path('admin/events/<int:event_id>/assign-bulk/', views.AdminEventAssignBulkView.as_view(), name='admin_event_assign_bulk'),
    path('admin/events/<int:event_id>/analytics/', views.AdminEventAnalyticsView.as_view(), name='admin_event_analytics'),
    path('admin/reports/', views.AdminReportsListView.as_view(), name='admin_reports'),
    path('admin/events/<int:event_id>/report/', views.AdminEventReportView.as_view(), name='admin_event_report'),
    path('admin/events/<int:event_id>/custom-fields/', views.EventCustomFieldsView.as_view(), name='event_custom_fields'),
    path('admin/events/<int:event_id>/api-keys/', views.AdminEventApiKeyListCreateView.as_view(), name='admin_event_api_keys'),
    path('admin/events/<int:event_id>/api-keys/<int:pk>/', views.AdminEventApiKeyDetailView.as_view(), name='admin_event_api_key_detail'),
]