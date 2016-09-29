from django.conf.urls import url, include
from django.contrib import admin
from . import views

urlpatterns = [
	
    url(r'^$', views.home, name='home'),
    url(r'^auth_error/', views.lti_auth_error, name='lti_auth_error'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^lti/', include('lti.urls', namespace="lti")),
    url(r'^quiz/', include('quiz.urls', namespace="quiz")),
    url(r'^qualtrics/', include('qualtrics.urls', namespace="qualtrics")),
    url(r'^engine/', include('engine.urls.urls', namespace="engine")),
    url(r'^api/', include('api.urls', namespace="api")),
    # url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
