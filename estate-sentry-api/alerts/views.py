from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from .models import Alert
from .serializers import AlertSerializer, AlertAcknowledgeSerializer


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and managing alerts.
    """
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return alerts for the current user."""
        queryset = Alert.objects.filter(user=self.request.user)

        # Filter by severity if provided
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity.upper())

        # Filter by acknowledged status
        acknowledged = self.request.query_params.get('acknowledged')
        if acknowledged is not None:
            is_acknowledged = acknowledged.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(acknowledged=is_acknowledged)

        return queryset

    @action(detail=True, methods=['patch'])
    def acknowledge(self, request, pk=None):
        """
        Mark an alert as acknowledged.
        PATCH /api/alerts/{id}/acknowledge/
        """
        alert = self.get_object()

        if alert.acknowledged:
            return Response(
                {'message': 'Alert already acknowledged'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AlertAcknowledgeSerializer(
            alert,
            data={},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()

        return Response(
            AlertSerializer(alert).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get alert statistics.
        GET /api/alerts/statistics/
        """
        user_alerts = Alert.objects.filter(user=request.user)

        stats = {
            'total_alerts': user_alerts.count(),
            'unacknowledged_alerts': user_alerts.filter(acknowledged=False).count(),
            'by_severity': dict(
                user_alerts.values('severity')
                .annotate(count=Count('id'))
                .values_list('severity', 'count')
            ),
            'recent_alerts': AlertSerializer(
                user_alerts.order_by('-timestamp')[:10],
                many=True
            ).data
        }

        return Response(stats)
