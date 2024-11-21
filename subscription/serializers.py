from rest_framework import serializers

from subscription.models import (Subscription, SubscriptionFeedback, Upsell,
                                 UserSubscription)


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'


class SubscriptionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['price_currency']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'subscription', 'date_started', 'expires', 'status']


class SubscriptionFeedbackSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField('email', read_only=True)

    class Meta:
        model = SubscriptionFeedback
        fields = ['comment', 'user', 'date_created']
class UpsellSerializer(serializers.ModelSerializer):
    chase = serializers.BooleanField()
    class Meta:
        model = Upsell
        fields = ['chase']
