# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-09-08 17:32
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ltilib", "0002_ltiparameters_lis_person_sourcedid"),
    ]

    operations = [
        migrations.RenameField(
            model_name="ltiparameters",
            old_name="canvas_course_id",
            new_name="custom_canvas_course_id",
        ),
        migrations.RenameField(
            model_name="ltiparameters",
            old_name="canvas_user_id",
            new_name="custom_canvas_user_id",
        ),
    ]
