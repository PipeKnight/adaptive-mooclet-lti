# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-06-07 15:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('engine', '0008_remove_quiz_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='quiz',
            name='url',
            field=models.CharField(default='', max_length=500),
        ),
    ]
