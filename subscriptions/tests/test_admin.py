from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.test import TestCase
from unittest.mock import patch

from contentstore.models import Schedule, MessageSet
from subscriptions.models import BehindSubscription, Subscription
from seed_stage_based_messaging import test_utils as utils


class TestBehindSubscriptionAdmin(TestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    def test_num_queries(self):
        """
        Ensure that we're not doing a query per row
        """
        schedule = Schedule.objects.create()
        messageset = MessageSet.objects.create(default_schedule=schedule)
        subscription = Subscription.objects.create(
            schedule=schedule, messageset=messageset)
        for i in range(5):
            BehindSubscription.objects.create(
                subscription=subscription, messages_behind=i,
                current_sequence_number=1, expected_sequence_number=1+i,
                current_messageset=messageset, expected_messageset=messageset)

        user = User.objects.create_superuser(
            "test", "test@example.org", "test")
        self.client.force_login(user)

        url = reverse("admin:subscriptions_behindsubscription_changelist")
        # 1: Session
        # 2: User
        # 3: List of messagesets for filtering
        # 4: Count of currently displayed items
        # 5: Count of total items
        # 6: List of behind subscriptions
        # 7: Number of messages behind for filtering
        with self.assertNumQueries(7):
            self.client.get(url)

    def test_find_behind_subscriptions_not_staff(self):
        """
        Redirects to admin login if the user isn't staff
        """
        user = User.objects.create_user("test")
        user.is_staff = False
        user.save()
        self.client.force_login(user)

        url = reverse("admin:find_behind_subscriptions")
        response = self.client.get(url)
        self.assertRedirects(response, "{}?next={}".format(
            reverse("admin:login"), url))

    @patch('subscriptions.admin.find_behind_subscriptions.delay')
    def test_find_behind_subscriptions_no_permission(self, task):
        """
        If the user is staff, but doesn't have permission to find behind
        subscriptions, it should redirect to the changelist view
        """
        user = User.objects.create_user("test")
        user.is_staff = True
        permission = Permission.objects.get(codename="view_behindsubscription")
        user.user_permissions.add(permission)
        user.save()
        self.client.force_login(user)

        url = reverse("admin:find_behind_subscriptions")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse("admin:subscriptions_behindsubscription_changelist"))
        task.assert_not_called()

    @patch('subscriptions.admin.find_behind_subscriptions.delay')
    def test_find_behind_subscription_valid(self, task):
        """
        Should run the task and redirect to the changelist view
        """
        user = User.objects.create_user("test")
        user.is_staff = True
        permission = Permission.objects.get(codename="view_behindsubscription")
        user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="can_find_behind_subscriptions")
        user.user_permissions.add(permission)
        user.save()
        self.client.force_login(user)

        url = reverse("admin:find_behind_subscriptions")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse("admin:subscriptions_behindsubscription_changelist"))
        task.assert_called_once_with()
