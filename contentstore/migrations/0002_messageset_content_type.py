# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-03-01 12:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contentstore", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="messageset",
            name="content_type",
            field=models.CharField(
                choices=[("text", "Text"), ("audio", "Audio")],
                default="text",
                max_length=20,
            ),
        )
    ]
