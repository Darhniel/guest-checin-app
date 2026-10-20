from rest_framework.throttling import AnonRateThrottle

class LoginThrottle(AnonRateThrottle):
    """
    Limits login attempts to 5 per minute per IP address.
    """
    scope = 'login'