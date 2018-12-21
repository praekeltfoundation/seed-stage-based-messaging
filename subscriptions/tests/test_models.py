from datetime import datetime

from django.test import TestCase

from contentstore.models import Message, MessageSet, Schedule
from seed_stage_based_messaging import test_utils as utils
from subscriptions.models import Subscription


class SubscriptionTest(TestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    def create_messageset_with_messages(self, name, schedule, n):
        """
        Creates and returns a messageset with n messages
        """
        messageset = MessageSet.objects.create(
            default_schedule=schedule, short_name=name
        )
        for i in range(n):
            Message.objects.create(
                messageset=messageset,
                text_content=str(i),
                sequence_number=(i + 1),
                lang="eng_ZA",
            )
        return messageset

    def test_messages_behind(self):
        """
        Ensures that it returns the correct number of messages behind
        """
        messageset1 = self.create_messageset_with_messages(
            "ms1", Schedule.objects.create(minute="0"), 2
        )
        messageset2 = self.create_messageset_with_messages(
            "ms2", Schedule.objects.create(), 0
        )
        messageset3 = self.create_messageset_with_messages(
            "ms3", Schedule.objects.create(minute="0", hour="*/2"), 2
        )
        messageset1.next_set = messageset2
        messageset1.save()
        messageset2.next_set = messageset3
        messageset2.save()

        # Should be on second message of 1st set, so 1 message behind
        start = datetime(2018, 1, 1, 0, 0, 0)
        end = datetime(2018, 1, 1, 1, 0, 0)
        sub = Subscription(
            created_at=start,
            messageset=messageset1,
            schedule=messageset1.default_schedule,
            lang="eng_ZA",
        )
        self.assertEqual(sub.messages_behind(end), 1)

        # Should be on first message of 3rd set, so 2 messages behind
        end = datetime(2018, 1, 1, 2, 0, 0)
        self.assertEqual(sub.messages_behind(end), 2)

        # Should be on second message of 3rd set, so 3 messages behind
        end = datetime(2018, 1, 1, 4, 0, 0)
        self.assertEqual(sub.messages_behind(end), 3)
