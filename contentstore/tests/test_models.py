# -*- coding: utf-8 -*-

from django.test import TestCase
from rest_framework.serializers import ValidationError

from ..models import Message, validate_special_characters
from .test_general import MessageSetTestMixin


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
    def test_raises_validation_error_for_special_chars(self):
        messageset = self.make_messageset()
        special_chars = u'This text has a special character – there'

        with self.assertRaises(ValidationError):
            m = Message.objects.create(
                sequence_number=1,
                messageset_id=messageset.id,
                text_content=special_chars,)
            m.full_clean()
