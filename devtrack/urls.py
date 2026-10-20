"""
Root URL configuration for the DevTrack project.

Every URL that starts with api/ is handed to the issues app, which defines
the actual endpoints in issues/urls.py.
"""
from django.urls import include, path

urlpatterns = [
    path('api/', include('issues.urls')),
]
