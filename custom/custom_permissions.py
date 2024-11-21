from typing import TYPE_CHECKING

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework import permissions
from rest_framework.request import Request

if TYPE_CHECKING:
    from custom.custom_viewsets import CustomGenericViewSet


class HasUnexpiredSubscription(permissions.BasePermission):
    """`True` if user has any subscription with `expires > timezone.now()`. `IsAuthenticated` is inherited."""
    message = 'User does not have unexpired subscriptions.'

    def has_permission(self, request: Request, view: 'CustomGenericViewSet'):
        user = request.user
        if not user or isinstance(user, AnonymousUser):
            return False
        subs = user.subscriptions   # User subscriptions are prefetched in the custom authentication backend
        return bool(subs.filter(expires__gte=timezone.now()).exists())
        # if not view.subscription_classes:
        #     return True
        # allowed_types = [c.subscription_type for c in view.subscription_classes]
        # for sub in subs.all():
        #     if sub.subscription.subscription_type in allowed_types:
        #         return True


class IsSelf(permissions.IsAuthenticated):
    """Permission is given if the view operates on the user that made the request. `IsAuthenticated` is inherited."""
    message = 'Invalid user id. Only own id allowed.'

    def has_object_permission(self, request, view, obj):
        return request.user == obj
