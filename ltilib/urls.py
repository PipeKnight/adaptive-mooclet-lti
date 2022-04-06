from django.conf.urls import url
from . import views

app_name = "ltilib"

urlpatterns = [
    url(r"^tool_config$", views.tool_config, name="tool_config"),
    url(r"^launch/(?P<quiz_id>[0-9]+)$", views.launch, name="launch"),
    url(
        r"^launch_resource_selection$",
        views.launch_resource_selection,
        name="launch_resource_selection",
    ),
    url(
        r"^launch_course_navigation$",
        views.launch_course_navigation,
        name="launch_course_navigation",
    ),
    url(
        r"^return_launch_url/(?P<quiz_id>[0-9]+)$",
        views.return_launch_url,
        name="return_launch_url",
    ),
    url(r"^exit$", views.exit, name="exit"),
]
