from django.db.models import Count
from django.core import exceptions
from django.core.management.base import BaseCommand
from django.utils.six.moves import input

from subscriptions.models import Subscription
from contentstore.models import MessageSet


def list_validator(valid_inputs):
    def validate(value):
        if value in valid_inputs:
            return value
        else:
            msg = "Selelection must be one of the following: {0}".format(
                str(valid_inputs))
            raise exceptions.ValidationError(msg, code='invalid_choice')

    return validate


class Command(BaseCommand):
    help = "Resets subscriptions status to ready."

    def get_option(self, value, option_format='[{0:>3}]'):
        return option_format.format(value)

    def handle(self, *args, **options):
        selection = None
        confirm = None

        stuck_subscriptions = Subscription.objects.filter(process_status=1)
        stuck_totals = stuck_subscriptions.values('messageset')\
            .annotate(total=Count('messageset')).order_by('messageset')

        self.stdout.write("Totals of stuck Subscriptions per MessageSet:")
        for total in stuck_totals:
            ms = MessageSet.objects.get(pk=total['messageset'])
            opt = self.get_option(ms.pk)
            line = "{opt} {name:<40} Total: {total:>6}".format(
                opt=opt,
                name=ms.short_name,
                total=total['total'])
            self.stdout.write(line)

        line = "{opt} {name:<40} Total: {total:>6}".format(
            opt=self.get_option('all'),
            name="All MessageSets",
            total=stuck_subscriptions.count())
        self.stdout.write(line)
        line = "{opt} Do nothing and quit".format(
            opt=self.get_option('q'),
            name="All MessageSets",
            total=stuck_subscriptions.count())
        self.stdout.write(line)

        msg = ("Please type the ID of the MessageSet you'd like to reset "
               "subscriptions for: ")
        valid_inputs = [str(o['messageset']) for o in stuck_totals]
        valid_inputs.extend(['all', 'q'])
        while selection is None:
            selection = self.get_input_data(msg, list_validator(valid_inputs))
            if selection == 'q':
                self.stdout.write("Quiting.")
                return

        if selection == 'all':
            records = stuck_subscriptions.all()
        else:
            records = stuck_subscriptions.filter(messageset=selection)

        msg = ("Do you wish to update these subscriptions to "
               "ready status? [y/n] ")
        while confirm is None:
            confirm = self.get_input_data(msg, list_validator(['y', 'n']))

        if confirm:
            rows_updated = records.update(process_status=0)
            msg = "Updated {0} rows to ready status".format(rows_updated)
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stdout.write("Ok, doing nothing.")

    def get_input_data(self, message, validator=None):
        raw_value = input(message)
        if validator is not None:
            try:
                val = validator(raw_value)
            except exceptions.ValidationError as e:
                self.stderr.write("Error: %s" % '; '.join(e.messages))
                val = None
        return val
