from django.http import JsonResponse

def api_root(request):
    return JsonResponse({
        "message": "Welcome to the Guest Check-in API",
        "status": "running",
        "endpoints": {
            "activity_log": "/api/activity-log/",
            "check_in": "/api/check-in/",
            "search": "/api/search-guests/",
            "admin": "/admin/"
        }
    })
