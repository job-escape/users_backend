from typing import Any, Dict

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from subscription.models import (
    UserSubscription,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    device_id = serializers.CharField(required=False)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        user_subscriptions = UserSubscription.objects.filter(user=user).order_by('-expires')
        if user_subscriptions.exists():
            token['subscriptions'] = []
            for user_subscription in user_subscriptions:
                token['subscriptions'].append({
                    'name': user_subscription.subscription.name,
                    'price': user_subscription.subscription.price_amount,
                    'currency': user_subscription.subscription.price_currency,
                    'expires': user_subscription.expires.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': user_subscription.status,
                })
        else:
            token['subscriptions'] = []
            
        return token

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, str]:
        if 'email' in attrs and not attrs['email'].islower():
            raise ValidationError('Email should be lowercase')
        data = super().validate(attrs)
        data['id'] = self.user.pk
        data['user_device_id'] = self.user.device_id
        data['device_id'] = attrs.get("device_id", None)
        return data
