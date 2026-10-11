from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from .models import Guest, Accreditation
from .serializers import GuestDetailSerializer, AccreditationSerializer

@api_view(['POST'])
def check_in(request):
    identifier = request.data.get('identifier', '').strip() # Accepts ticket_number or name
    if not identifier:
        return Response({'status': 400, 'message': 'Please provide ticket number or name'}, status=400)

    guest = Guest.objects.filter(
        Q(adult_names__iexact=identifier) | Q(ticket_number__iexact=identifier)
    ).first()

    if not guest:
        return Response({'status': 404, 'message': 'Guest not found'}, status=404)

    today = timezone.localdate()
    
    existing = Accreditation.objects.filter(
        guest=guest, is_accredited=True, date__date=today,
    ).exists()

    if existing:
        return Response({'status': 400, 'message': 'This guest has already been checked in today'}, status=400)

    # Create accreditation record
    Accreditation.objects.create(guest=guest, is_accredited=True)
    guest_serializer = GuestDetailSerializer(guest)

    return Response({
        'status': 200,
        'message': 'Guest checked in successfully',
        'guest': guest_serializer.data
    })

@api_view(['GET'])
def activity_log(request):
    today = timezone.localdate()
    accreditations = Accreditation.objects.filter(
        date__date=today
    ).order_by('-date', '-time')[:20] # Last 20
    
    serializer = AccreditationSerializer(accreditations, many=True)
    return Response({'status': 200, 'data': serializer.data})

@api_view(['GET'])
def search_guests(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 3:
        return Response({'status': 200, 'data': []})

    today = timezone.localdate()

    guests = Guest.objects.filter(adult_names__icontains=query).order_by('adult_names')[:10]

    accredited_ids = set(Accreditation.objects.filter(
        guest__in=guests, date__date=today, is_accredited=True
    ).values_list('guest_id', flat=True))

    results = []
    for guest in guests:
        results.append({
            'id': guest.adult_names,
            'ticket_number': guest.ticket_number,
            'email': guest.email,
            'phone': guest.phone,
            'ok': guest.id not in accredited_ids,
            'kids_count': guest.kids.count(),
        })

    return Response({'status': 200, 'data': results})
