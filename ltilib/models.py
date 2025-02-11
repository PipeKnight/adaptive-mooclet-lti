from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models
from engine.models import Quiz


class LtiParameters(models.Model):
    """
    Used to store outcome service url for a particular user and quiz
    Enables asynchronous or API-triggered grade passback
    """

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    quiz = models.ForeignKey(Quiz, on_delete=models.DO_NOTHING)

    # LTI params - ADD THESE BELOW TOO
    lis_outcome_service_url = models.CharField(max_length=1024, default="")
    lis_result_sourcedid = models.CharField(max_length=1024, default="")
    oauth_consumer_key = models.CharField(max_length=1024, default="")
    lis_person_sourcedid = models.CharField(
        max_length=1024, default=""
    )  # HUID if launching tool from canvas
    custom_canvas_user_id = models.CharField(max_length=1024, default="")
    custom_canvas_course_id = models.CharField(max_length=1024, default="")
    roles = models.CharField(max_length=1024, default="")
    context_id = models.CharField(max_length=1024, default="")

    # used to enable iteration through parameter names to make saving these easier
    parameter_names = [
        "lis_outcome_service_url",
        "lis_result_sourcedid",
        "oauth_consumer_key",
        "lis_person_sourcedid",
        "custom_canvas_user_id",
        "custom_canvas_course_id",
        "roles",
        "context_id",
    ]

    # TODO may want to collect other LTI params

    # corresponds to "user_id" LTI param (hashed field), field renamed so it's not confused with user foreign key
    lti_user_id = models.CharField(max_length=100, default="")

    # generic text field where all LTI params are dumped as json
    data = models.TextField(default="")

    class Meta:
        unique_together = ("user", "quiz")
        verbose_name = "LTI Parameters"
        verbose_name_plural = "LTI Parameters"
