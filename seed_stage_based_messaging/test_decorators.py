from django.test import TestCase
from django.urls import reverse
from rest_framework import status


class InternalOnlyTests(TestCase):
    def test_internal_access(self):
        """
        Internal access should be allowed
        """
        url = reverse("metrics")
        response = self.client.get(url, HTTP_X_FORWARDED_FOR="1.2.3.4")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_external_access(self):
        """
        External access through the load balancer should be blocked
        """
        url = reverse("metrics")
        response = self.client.get(url, HTTP_X_FORWARDED_FOR="1.2.3.4, 4.3.2.1")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
