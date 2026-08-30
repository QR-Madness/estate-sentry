from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SensorReadingViewSet, SensorViewSet

app_name = 'sensors'

router = DefaultRouter()
router.register(r'sensors', SensorViewSet, basename='sensor')
router.register(r'readings', SensorReadingViewSet, basename='reading')

urlpatterns = [
    path('', include(router.urls)),
]
