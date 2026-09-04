from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ZoneAdjacencyViewSet,
    ZonePerimeterViewSet,
    ZoneRuleViewSet,
    ZoneViewSet,
)

router = DefaultRouter()
router.register(r"zones", ZoneViewSet, basename="zone")
router.register(r"zone-perimeters", ZonePerimeterViewSet, basename="zoneperimeter")
router.register(r"zone-rules", ZoneRuleViewSet, basename="zonerule")
router.register(r"zone-adjacency", ZoneAdjacencyViewSet, basename="zoneadjacency")

urlpatterns = [path("", include(router.urls))]
