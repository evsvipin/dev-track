"""
URL routes for the issues app.

These paths are mounted under api/ by devtrack/urls.py, so the full URLs are
/api/reporters/ and /api/issues/. Query parameters (?id=1, ?status=open) are
read inside the views, not declared here.
"""
from django.urls import path

from issues import views

urlpatterns = [
    path('reporters/', views.reporters, name='reporters'),
    path('issues/', views.issues, name='issues'),
]
