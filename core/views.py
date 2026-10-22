from django.http import JsonResponse
from django.urls import get_resolver


def _collect_endpoints(patterns, prefix=""):
    """Recursively flatten URL patterns into absolute path strings."""
    endpoints = []
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):  # an included URLconf
            endpoints.extend(_collect_endpoints(pattern.url_patterns, route))
        else:
            endpoints.append("/" + route)
    return endpoints


def api_root(request):
    # Built from the live URLconf so this list always matches the real routes.
    endpoints = [
        path for path in _collect_endpoints(get_resolver().url_patterns)
        if path.startswith("/api/")
    ]
    return JsonResponse({
        "message": "Welcome to the Guest Check-in API",
        "status": "running",
        "endpoints": sorted(endpoints),
        "admin": "/admin/"
    })
