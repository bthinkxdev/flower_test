"""URL routing for the corporate app."""

from __future__ import annotations

from django.urls import path

from corporate import views

app_name = "corporate"

urlpatterns = [
    path("dashboard/", views.corporate_dashboard_view, name="dashboard"),
]
