# -*- coding: utf-8 -*-

from django.test import TestCase
from rest_framework.serializers import ValidationError

from ..models import Message, validate_special_characters
from .test_general import MessageSetTestMixin
from seed_stage_based_messaging import test_utils as utils


class TestValidators(TestCase):
    def test_special_characters_allows_normal_text(self):
        self.assertEqual(validate_special_characters('ascii text!'), None)

    def test_special_characters_rejects_bad_chars(self):
        with self.assertRaises(ValidationError):
            validate_special_characters(u'I said “hello"')

        with self.assertRaises(ValidationError):
            validate_special_characters(u'I said "hello”')

        with self.assertRaises(ValidationError):
            validate_special_characters(u'It’s over there')

        with self.assertRaises(ValidationError):
            validate_special_characters(u'Hello –')


class TestMessage(MessageSetTestMixin, TestCase):
    def setUp(self):
        utils.disable_signals()

    def tearDown(self):
        utils.enable_signals()

    def test_raises_validation_error_for_special_chars(self):
        messageset = self.make_messageset()
        special_chars = u'This text has a special character – there'

        with self.assertRaises(ValidationError):
            m = Message.objects.create(
                sequence_number=1,
                messageset_id=messageset.id,
                text_content=special_chars,)
            m.full_clean()

    def test_raises_validation_error_for_whatsapp_invalid_chars(self):
        """
        Should raise a validation error if any of the disallowed characters
        are present in the text content.
        """
        messageset = self.make_messageset(channel='TEST_WHATSAPP_CHANNEL')
        messages = [
            "Message with \n newline",
            "Message with \t tab",
            "Message with    four spaces",
        ]
        for message in messages:
            with self.assertRaises(ValidationError):
                Message.objects.create(
                    sequence_number=1,
                    messageset_id=messageset.id,
                    text_content=message,
                )
