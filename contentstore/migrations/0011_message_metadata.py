# Generated by Django 2.1.2 on 2019-02-20 15:47

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("contentstore", "0010_auto_20181126_1104")]

    operations = [
        migrations.AddField(
            model_name="message",
            name="metadata",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        )
    ]
