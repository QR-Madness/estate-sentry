"""HQ dashboard routes.

Served from the same origin as the API, which is why there is no CORS story and
no separate frontend service to deploy.
"""

from django.urls import path

from . import views

app_name = "hq"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cameras/<str:camera_id>/mjpeg", views.camera_mjpeg, name="camera-mjpeg"),
    path("events/stream", views.events_stream, name="events-stream"),
]
