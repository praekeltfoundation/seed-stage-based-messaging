from django.test import TestCase

from .utils import normalise_metric_name


class NormaliseMetricNameTest(TestCase):
    def test_normalise_metric_name(self):
        """
        The normalise_metric_name function should replace all non-alphanumeric
        with underscores.
        """
        self.assertEqual(normalise_metric_name('foo^& bar'), 'foo_bar')
        self.assertEqual(normalise_metric_name('foo   bar'), 'foo_bar')
        self.assertEqual(normalise_metric_name('_foo!bar,'), 'foo_bar')
