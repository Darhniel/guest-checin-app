from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from .models import CustomUser, Event


class ConsoleRolePermissionTests(APITestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            email='admin@example.com',
            full_name='Full Admin',
            password='test-password',
            role=CustomUser.ROLE_ADMIN,
        )
        self.supervisor = CustomUser.objects.create_user(
            email='supervisor@example.com',
            full_name='Supervisor',
            password='test-password',
            role=CustomUser.ROLE_SUPERVISOR,
        )
        self.event = Event.objects.create(
            name='Existing event',
            start_date=date.today(),
            end_date=date.today(),
            created_by=self.admin,
        )

    def test_supervisor_can_view_events_but_cannot_create_or_edit_them(self):
        self.client.force_authenticate(user=self.supervisor)

        self.assertEqual(self.client.get('/api/events/').status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.post('/api/events/', {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        response = self.client.patch(
            f'/api/events/{self.event.id}/',
            {'name': 'Changed by supervisor'},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.event.refresh_from_db()
        self.assertEqual(self.event.name, 'Existing event')

    def test_supervisor_cannot_create_ambassadors(self):
        self.client.force_authenticate(user=self.supervisor)

        response = self.client.post('/api/admin/ambassadors/', {})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_create_console_users_or_event_resources(self):
        self.client.force_authenticate(user=self.supervisor)

        admin_response = self.client.post(
            '/api/admin/admins/',
            {
                'email': 'new-supervisor@example.com',
                'full_name': 'New Supervisor',
                'password': 'test-password',
                'role': CustomUser.ROLE_SUPERVISOR,
            },
            format='json',
        )
        location_response = self.client.post(
            f'/api/events/{self.event.id}/locations/',
            {'name': 'New entrance'},
            format='json',
        )
        category_response = self.client.post(
            f'/api/events/{self.event.id}/categories/',
            {'name': 'New category'},
            format='json',
        )

        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(location_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(category_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_admin_can_create_events_and_ambassadors(self):
        self.client.force_authenticate(user=self.admin)

        event_response = self.client.post(
            '/api/events/',
            {
                'name': 'New event',
                'start_date': date.today().isoformat(),
                'end_date': date.today().isoformat(),
            },
            format='json',
        )
        ambassador_response = self.client.post(
            '/api/admin/ambassadors/',
            {
                'email': 'ambassador@example.com',
                'full_name': 'New Ambassador',
                'password': 'test-password',
            },
            format='json',
        )

        self.assertEqual(event_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ambassador_response.status_code, status.HTTP_201_CREATED)

    def test_full_admin_can_create_supervisor_and_get_expected_response(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/admin/admins/',
            {
                'email': 'new-supervisor@example.com',
                'full_name': 'New Supervisor',
                'password': 'test-password',
                'role': CustomUser.ROLE_SUPERVISOR,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], CustomUser.ROLE_SUPERVISOR)
        self.assertEqual(response.data['user']['first_login'], True)
