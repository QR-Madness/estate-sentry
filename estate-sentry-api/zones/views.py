"""Zone API.

The perception service is a client of these endpoints, not just the dashboard:
it fetches zones and their perimeters on startup and caches them, per
`docs/Specification.md`.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Zone, ZoneAdjacency, ZonePerimeter, ZoneRule
from .serializers import (
    ZoneAdjacencySerializer,
    ZonePerimeterSerializer,
    ZoneRuleSerializer,
    ZoneSerializer,
)


class ZoneViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Prefetched because the perception service reads the whole list with
        # perimeters on every startup; without it that is a query per zone.
        return (
            Zone.objects.filter(owner=self.request.user)
            .prefetch_related("perimeters", "perimeters__camera", "rules")
        )

    @action(detail=True, methods=["get", "post"])
    def perimeters(self, request, pk=None):
        zone = self.get_object()
        if request.method == "GET":
            return Response(
                ZonePerimeterSerializer(zone.perimeters.all(), many=True).data
            )
        serializer = ZonePerimeterSerializer(data={**request.data, "zone": zone.pk})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def rules(self, request, pk=None):
        zone = self.get_object()
        if request.method == "GET":
            return Response(ZoneRuleSerializer(zone.rules.all(), many=True).data)
        serializer = ZoneRuleSerializer(data={**request.data, "zone": zone.pk})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ZonePerimeterViewSet(viewsets.ModelViewSet):
    serializer_class = ZonePerimeterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ZonePerimeter.objects.filter(zone__owner=self.request.user)


class ZoneRuleViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ZoneRule.objects.filter(zone__owner=self.request.user)


class ZoneAdjacencyViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneAdjacencySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ZoneAdjacency.objects.filter(from_zone__owner=self.request.user)
