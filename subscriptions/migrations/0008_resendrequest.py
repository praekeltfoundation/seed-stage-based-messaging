# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2018-02-01 09:03
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contentstore', '0007_auto_20171102_0950'),
        ('subscriptions', '0007_auto_20171102_0950'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResendRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('outbound', models.UUIDField(null=True)),
                ('message', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='resend_requests', to='contentstore.Message')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subscriptions.Subscription')),
            ],
        ),
    ]
