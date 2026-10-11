from django.urls import path
from . import views

urlpatterns = [
    path("api/search-guests/", views.search_guests, name="api_search_guests"),
    path("api/check-in/", views.check_in, name="api_check_in"),
    path("api/activity-log/", views.activity_log, name="api_activity_log"),
]
