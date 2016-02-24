# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-09 13:14
from __future__ import unicode_literals

import contentstore.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BinaryContent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.FileField(upload_to=contentstore.models.generate_new_filename)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence_number', models.IntegerField()),
                ('lang', models.CharField(max_length=6)),
                ('text_content', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('binary_content', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='message', to='contentstore.BinaryContent')),
            ],
            options={
                'ordering': ['sequence_number'],
            },
        ),
        migrations.CreateModel(
            name='MessageSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('short_name', models.CharField(max_length=20, unique=True, verbose_name='Short name')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('minute', models.CharField(default='*', max_length=64, verbose_name='minute')),
                ('hour', models.CharField(default='*', max_length=64, verbose_name='hour')),
                ('day_of_week', models.CharField(default='*', max_length=64, verbose_name='day of week')),
                ('day_of_month', models.CharField(default='*', max_length=64, verbose_name='day of month')),
                ('month_of_year', models.CharField(default='*', max_length=64, verbose_name='month of year')),
            ],
            options={
                'verbose_name_plural': 'schedules',
                'ordering': ['month_of_year', 'day_of_month', 'day_of_week', 'hour', 'minute'],
                'verbose_name': 'schedule',
            },
        ),
        migrations.AddField(
            model_name='messageset',
            name='default_schedule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_sets', to='contentstore.Schedule'),
        ),
        migrations.AddField(
            model_name='messageset',
            name='next_set',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contentstore.MessageSet'),
        ),
        migrations.AddField(
            model_name='message',
            name='messageset',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='contentstore.MessageSet'),
        ),
    ]