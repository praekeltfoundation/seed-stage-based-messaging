# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-01 12:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contentstore", "0007_auto_20171102_0950")]

    operations = [
        migrations.AddField(
            model_name="schedule",
            name="scheduler_schedule_id",
            field=models.UUIDField(
                blank=True,
                default=None,
                null=True,
                verbose_name="scheduler schedule id",
            ),
        )
    ]
