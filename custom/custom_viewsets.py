from typing import List

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from account.models import CustomUser
from subscription.models import SubscriptionType
from web_analytics.event_manager import EventManager
# from web_analytics.tasks import bindDeviceToUser
from google_tasks.tasks import create_bind_device_task


class CustomGenericViewSet(GenericViewSet):
    subscription_classes: List[SubscriptionType] = []

    def get_permissions(self):
        return super().get_permissions()
        # if settings.DEBUG:
        #     return super().get_permissions()
        # if self.permission_classes:
        #     self.permission_classes.append(IsAuthenticated) if IsAuthenticated not in self.permission_classes else None
        #     self.permission_classes.append(HasUnexpiredSubscription)
        #     return super().get_permissions()
        # return [p() for p in [IsAuthenticated, HasUnexpiredSubscription]]


class CustomReadOnlyModelViewSet(mixins.RetrieveModelMixin,
                                 mixins.ListModelMixin,
                                 CustomGenericViewSet):
    """
    A viewset that provides default `list()` and `retrieve()` actions with subscription-based access.
    """
    pass


class CustomTokenObtainPairView(TokenObtainPairView):
    @extend_schema(
        responses=inline_serializer("jwt_serializer", fields={
            "refresh": serializers.CharField(),
            "access": serializers.CharField(),
            "id": serializers.IntegerField(),
            "device_id": serializers.CharField(),
        })
    )
    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])  # pylint: disable=w0707

        data = serializer.validated_data
        device_id = data['device_id']
        if device_id is not None:
            if device_id != data.get("user_device_id"):
                # bindDeviceToUser.delay(device_id, data['id'])
                create_bind_device_task(device_id, data['id'])
                
                CustomUser.objects.filter(id=data['id']).update(device_id=device_id)
        EventManager().sendEvent("pr_webapp_user_signined", data['id'], topic="app")
        return Response(serializer.validated_data)
