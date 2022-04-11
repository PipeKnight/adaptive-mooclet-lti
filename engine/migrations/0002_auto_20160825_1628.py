# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-25 16:28
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("engine", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="variable",
            name="display_name",
            field=models.CharField(default="", max_length=200),
        ),
        migrations.AlterField(
            model_name="answer",
            name="mooclet_explanation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="engine.Mooclet",
            ),
        ),
    ]
