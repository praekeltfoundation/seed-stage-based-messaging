from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from contentstore.models import MessageSet, Schedule
from seed_stage_based_messaging import test_utils as utils
from subscriptions.models import BehindSubscription, Subscription


class SubscriptionSendViewTests(APITestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    @patch("subscriptions.views.schedule_disable")
    def test_disables_schedule(self, disable_schedule):
        """
        The subscription send view should disable the schedule for the
        subscription
        """
        schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        subscription = Subscription.objects.create(
            schedule=schedule, messageset=messageset
        )
        url = reverse("subscription-send", args=[str(subscription.id)])

        user = User.objects.create_user("test")
        self.client.force_authenticate(user=user)

        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        disable_schedule.delay.assert_called_once_with(str(subscription.id))


class BehindSubscriptionViewSetTests(APITestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    def test_unauthenticated(self):
        """
        Unauthenticated requests should not be allowed
        """
        url = reverse("behindsubscription-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        url = reverse("behindsubscription-find-behind-subscriptions")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_permissions(self):
        """
        If the user doesn't have the required permissions, the request should
        be denied.
        """
        user = User.objects.create_user("test")
        self.client.force_authenticate(user=user)

        url = reverse("behindsubscription-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        url = reverse("behindsubscription-find-behind-subscriptions")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_disallowed_methods(self):
        """
        Creating, updating, and deleting should not be allowed
        """
        user = User.objects.create_user("test")
        self.client.force_authenticate(user=user)

        url = reverse("behindsubscription-list")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        url = reverse("behindsubscription-detail", args=(1,))
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        url = reverse("behindsubscription-find-behind-subscriptions")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_view_permission(self):
        """
        The view permission should allow listing and viewing, but should
        still disallow the actions.
        """
        user = User.objects.create_user("test")
        permission = Permission.objects.get(codename="view_behindsubscription")
        user.user_permissions.add(permission)
        self.client.force_authenticate(user=user)

        schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        subscription = Subscription.objects.create(
            schedule=schedule, messageset=messageset
        )
        # test paginattion size is set to 2
        for i in range(3):
            behind = BehindSubscription.objects.create(
                subscription=subscription,
                messages_behind=i,
                current_sequence_number=1,
                expected_sequence_number=1 + i,
                current_messageset=messageset,
                expected_messageset=messageset,
            )

        url = reverse("behindsubscription-list")
        # Ensure we're not doing a query per row
        # 1: Get permissions for user
        # 2: Get permissions from user's groups
        # 3: Get list of behind subscriptions
        with self.assertNumQueries(3):
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = reverse("behindsubscription-detail", args=(behind.id,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = reverse("behindsubscription-find-behind-subscriptions")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("subscriptions.views.find_behind_subscriptions.delay")
    def test_action_permission(self, find_behind_subscriptions):
        """
        The permission to perform the find-behind-subscriptions action should
        allow the user to perform the action, but still disallow them from
        listing/detailing the behind subscriptions
        """
        find_behind_subscriptions.return_value = "task-id"

        user = User.objects.create_user("test")
        permission = Permission.objects.get(codename="can_find_behind_subscriptions")
        user.user_permissions.add(permission)
        self.client.force_authenticate(user=user)

        schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        subscription = Subscription.objects.create(
            schedule=schedule, messageset=messageset
        )
        behind = BehindSubscription.objects.create(
            subscription=subscription,
            messages_behind=1,
            current_sequence_number=1,
            expected_sequence_number=2,
            current_messageset=messageset,
            expected_messageset=messageset,
        )

        url = reverse("behindsubscription-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        url = reverse("behindsubscription-detail", args=(behind.id,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        url = reverse("behindsubscription-find-behind-subscriptions")
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data, {"accepted": True, "task_id": "task-id"})
