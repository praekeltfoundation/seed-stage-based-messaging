# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-24 08:22
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("subscriptions", "0001_initial")]

    operations = [
        migrations.RenameField(
            model_name="subscription", old_name="contact", new_name="identity"
        )
    ]
