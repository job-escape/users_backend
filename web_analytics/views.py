from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class HealthcheckViewSet(viewsets.GenericViewSet):
    """The viewset for the healthcheck pinging."""
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: None})
    def list(self, request):
        assert request.user
        return Response({"status": "OK"})
