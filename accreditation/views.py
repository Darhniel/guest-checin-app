# from django.shortcuts import render
# import logging
# from datetime import timedelta
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.utils import timezone
# from django.db.models import Q
# from .models import Guest, Accreditation
# logger = logging.getLogger(__name__)


# # Accreditation
# def accreditation(request):
#     return render(request, 'accreditation.html')

# # Search Guests
# def search_guests(request):
#     """Search for guests by adult names"""
#     if request.method == 'GET':
#         query = request.GET.get('q', '').strip()

#         if len(query) >= 3:
#             guest_results = Guest.objects.filter(adult_names__icontains=query).order_by('adult_names')

#             ticket_list = []

#             # Get today's accreditations
#             today = timezone.now().date()
#             tomorrow = today + timedelta(days=1)
#             guest_accreditations = set(Accreditation.objects.filter(
#                 guest__in=guest_results,
#                 date__gte=today,
#                 date__lt=tomorrow,
#                 is_accredited=True
#             ).values_list('guest_id', flat=True))

#             # Process Guest results
#             for guest in guest_results:
#                 ticket_list.append({
#                     'id': guest.id,
#                     'name': guest.adult_names,
#                     'email': guest.email,
#                     'phone': guest.phone,
#                     'type': 'guest',
#                     'total_quantity': 1,
#                     'is_accredited': guest.id in guest_accreditations,
#                     'kids_count': guest.kids.count(),
#                 })

#             return JsonResponse({'tickets': ticket_list})
#         else:
#             return JsonResponse({'tickets': []})

#     return JsonResponse({'status': 405, 'message': 'Method Not Allowed!'})

# # Activity Log
# @csrf_exempt
# def activity_log(request):
#     if request.method == 'GET':
#         events = []
#         for acc in Accreditation.objects.select_related('guest').order_by('-date', '-time')[:50]:
#             guest_name = acc.guest.adult_names if acc.guest else 'Unknown'
#             kids_count = acc.guest.kids.count() if acc.guest else 0
#             events.append({
#                 'name': guest_name,
#                 'kids_count': kids_count,
#                 'ok': acc.is_accredited,
#                 'time': acc.time.strftime('%H:%M:%S') if acc.time else '',
#                 'date': acc.date.strftime('%d/%m/%Y') if acc.date else '',
#             })
#         return JsonResponse({'events': events})
#     return JsonResponse({'status': 405, 'message': 'Method Not Allowed!'})

# # Check In
# @csrf_exempt
# def check_in(request):
#     if request.method == 'POST':
#         name = request.POST.get('name') or request.POST.get('unique_code', '').strip()
#         quantity_str = request.POST.get('quantity')
#         accredit_all = request.POST.get('accredit_all') == 'true'

#         if not name:
#             return JsonResponse({'status': 400, 'message': 'Please provide ticket name'})

#         # Try to find Guest by adult_names or ticket number
#         guest = Guest.objects.filter(
#             Q(adult_names__iexact=name) | Q(ticket_number__iexact=name)
#         ).first()

#         if not guest:
#             return JsonResponse({'status': 404, 'message': 'Guest not found'})

#         # Handle Guest check-in
#         if guest:
#             # Check if already accredited today
#             today = timezone.now().date()
#             tomorrow = today + timedelta(days=1)
#             existing_accreditation = Accreditation.objects.filter(
#                 guest=guest,
#                 is_accredited=True,
#                 date__gte=today,
#                 date__lt=tomorrow
#             ).first()

#             if quantity_str:
#                 # Process check-in with quantity
#                 if existing_accreditation:
#                     return JsonResponse({'status': 400, 'message': 'This Guest has already been checked in today'})

#                 # Check in the Guest
#                 Accreditation.objects.create(
#                     guest=guest,
#                     is_accredited=True
#                 )

#                 kids = [{'name': kid.name, 'age': kid.age, 'gender': kid.gender} for kid in guest.kids.all()]
#                 return JsonResponse({
#                     'status': 200,
#                     'message': 'Guest checked in successfully',
#                     'guest': {
#                         'adult_names': guest.adult_names,
#                         'spouse_name': guest.spouse_name,
#                         'nanny_name': guest.nanny_name,
#                         'email': guest.email,
#                         'phone': guest.phone,
#                         'kids': kids,
#                         'accredited_quantity': 1,
#                         'total_quantity': 1,
#                         'type': 'guest'
#                     }
#                 })
#             else:
#                 # Return ticket info for modal
#                 is_accredited_today = existing_accreditation is not None
#                 kids = [{'name': kid.name, 'age': kid.age, 'gender': kid.gender} for kid in guest.kids.all()]
#                 ticket_info = {
#                     'name': guest.adult_names,
#                     'email': guest.email,
#                     'phone': guest.phone,
#                     'spouse_name': guest.spouse_name,
#                     'nanny_name': guest.nanny_name,
#                     'allergies': guest.allergies,
#                     'kids': kids,
#                     'is_accredited_today': is_accredited_today,
#                     'type': 'guest'
#                 }
#                 return JsonResponse({'status': 200, 'ticket': ticket_info})

#     return JsonResponse({'status': 405, 'message': 'Method not allowed'})

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

    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    existing = Accreditation.objects.filter(
        guest=guest, is_accredited=True, date__gte=today, date__lt=tomorrow
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
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    accreditations = Accreditation.objects.filter(
        date__gte=today, date__lt=tomorrow
    ).order_by('-date', '-time')[:20] # Last 20
    
    serializer = AccreditationSerializer(accreditations, many=True)
    return Response({'status': 200, 'data': serializer.data})

@api_view(['GET'])
def search_guests(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 3:
        return Response({'status': 200, 'data': []})

    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    guests = Guest.objects.filter(adult_names__icontains=query).order_by('adult_names')[:10]

    accredited_ids = set(Accreditation.objects.filter(
        guest__in=guests, date__gte=today, date__lt=tomorrow, is_accredited=True
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