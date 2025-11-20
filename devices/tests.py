from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Device, UserProfile
from .services import apply_device_filters

User = get_user_model()


class BaseTestCase(TestCase):
    def create_user(self, username='user', role=UserProfile.Roles.GUEST, can_delete=True, **kwargs):
        password = kwargs.pop('password', 'pass12345')
        user = User.objects.create_user(username=username, password=password, **kwargs)
        profile = user.profile
        profile.role = role
        profile.can_delete_devices = can_delete
        profile.save()
        user._plain_password = password  # Helper for login
        return user


class DeviceModelTests(BaseTestCase):
    def test_soft_delete_creates_history_and_sets_trash(self):
        user = self.create_user(role=UserProfile.Roles.ADMIN)
        device = Device.objects.create(imei='123456789012345', model_name='Test', added_by=user)

        self.assertIsNone(device.deleted_at)
        self.assertEqual(device.status, Device.STATUS_IN_STOCK)

        device.soft_delete(user=user)
        device.refresh_from_db()

        self.assertEqual(device.status, Device.STATUS_TRASH)
        self.assertIsNotNone(device.deleted_at)
        self.assertEqual(device.history.count(), 1)

        device.restore(user=user)
        device.refresh_from_db()
        self.assertEqual(device.status, Device.STATUS_IN_STOCK)
        self.assertIsNone(device.deleted_at)


class FilterServiceTests(BaseTestCase):
    def test_apply_device_filters_by_user_and_dates(self):
        admin = self.create_user(username='admin', role=UserProfile.Roles.ADMIN)
        operator = self.create_user(username='operator', role=UserProfile.Roles.OPERATOR)
        base_time = timezone.now() - timedelta(days=5)
        Device.objects.create(imei='123456789012345', model_name='Alpha', added_by=admin, date_added=base_time)
        Device.objects.create(imei='123456789012346', model_name='Beta', added_by=operator, date_added=timezone.now())

        queryset = Device.objects.all()
        params = {
            'added_by': str(operator.id),
            'date_from': (timezone.now() - timedelta(days=1)).date().isoformat(),
        }
        filtered = apply_device_filters(queryset, params)
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().added_by, operator)


class ImeiLookupViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.operator = self.create_user(username='operator', role=UserProfile.Roles.OPERATOR)

    def test_lookup_requires_authentication(self):
        response = self.client.get(reverse('imei_lookup'), {'imei': '123456789012345'})
        self.assertEqual(response.status_code, 302)  # Redirect to login

    @patch('devices.views.lookup_device_by_imei')
    def test_lookup_returns_payload(self, mock_lookup):
        mock_lookup.return_value = type(
            'Resp',
            (),
            {
                'imei': '123456789012345',
                'brand': 'Test',
                'model': 'Model',
                'model_name': 'Model',
                'formatted_name': '(Test) - Model',
            },
        )()
        self.client.login(username=self.operator.username, password=self.operator._plain_password)
        response = self.client.get(reverse('imei_lookup'), {'imei': '123456789012345'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        mock_lookup.assert_called_once()
