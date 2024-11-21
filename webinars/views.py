

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from custom.custom_exceptions import BadRequest
from custom.custom_permissions import HasUnexpiredSubscription
from webinars.models import Webinar
from webinars.serializers import (WebinarListSerializer,
                                  WebinarRequestSerializer, WebinarSerializer)


class WebinarViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """The viewset for retrieving Webinars information."""
    queryset = Webinar.objects.all()
    permission_classes = [HasUnexpiredSubscription]

    def get_serializer_class(self):
        if self.action == 'list':
            return WebinarListSerializer
        return WebinarSerializer

    @extend_schema(parameters=[WebinarRequestSerializer])
    def list(self, request: Request, *args, **kwargs):
        if not request.query_params:
            raise BadRequest('Status is required in request query parameters.')
        ser = WebinarRequestSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        queryset = self.get_queryset()
        queryset = queryset.filter(status=request.query_params['status'])
        ser2 = self.get_serializer(queryset, many=True)
        return Response(ser2.data)
