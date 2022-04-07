from django.conf.urls import include, url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r"^$", views.home, name="home"),
    url(r"^auth_error/", views.lti_auth_error, name="lti_auth_error"),
    url(r"^admin/", admin.site.urls),
    url(r"^lti/", include("ltilib.urls", namespace="lti")),
    url(r"^quiz/", include("quiz.urls", namespace="quiz")),
    url(r"^qualtrics/", include("qualtrics.urls", namespace="qualtrics")),
    url(r"^engine/", include("engine.urls.urls", namespace="engine")),
    url(r"^api/", include("api.urls", namespace="api")),
    # url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

import debug_toolbar

urlpatterns += [
    url(r"^__debug__/", include(debug_toolbar.urls)),
]
