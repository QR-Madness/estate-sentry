"""Zone event log API."""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ZoneEvent
from .serializers import ZoneEventBulkSerializer, ZoneEventSerializer


class ZoneEventViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Read the log, and append to it.

    No update or delete, deliberately. This is an evidence log: entries are
    written once by the pipeline and read afterwards. Editing history through
    the same API that writes it would undermine the point of keeping it.
    """

    serializer_class = ZoneEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ZoneEvent.objects.filter(
            zone__owner=self.request.user
        ).select_related("zone", "camera")

        zone = self.request.query_params.get("zone")
        if zone:
            queryset = queryset.filter(zone_id=zone)
        object_class = self.request.query_params.get("object_class")
        if object_class:
            queryset = queryset.filter(object_class=object_class)
        since = self.request.query_params.get("since")
        if since:
            queryset = queryset.filter(timestamp__gte=since)
        return queryset

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request):
        """Append several events at once. See ZoneEventBulkSerializer."""
        serializer = ZoneEventBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"created": len(result["events"])}, status=status.HTTP_201_CREATED
        )
