
from rest_framework import serializers

from custom.custom_serializer_fields import EmailField
from payment_checkout.models import CheckoutPaymentMethod
from subscription.models import TrialPriceChoices


class CheckoutPaymentRequestSerializer(serializers.Serializer):
    email = EmailField()
    subscription_id = serializers.IntegerField()
    trial_type = serializers.ChoiceField(choices=TrialPriceChoices.choices)
    token = serializers.CharField()
    ip = serializers.CharField()
    name = serializers.CharField(allow_blank=True, default="")
    country_code = serializers.CharField()
    device_session_id = serializers.CharField()


class CheckoutCheckRequestSerializer(serializers.Serializer):
    pay_id = serializers.CharField()


class CheckoutPaymentResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    fb_event_id = serializers.CharField()


class CheckoutPayment3dsSerializer(serializers.Serializer):
    href = serializers.CharField()
    pay_id = serializers.CharField()


class ValidateApplePaySerializer(serializers.Serializer):
    appleUrl = serializers.CharField()


class CheckoutApplePaySerializer(serializers.Serializer):
    email = EmailField()
    subscription_id = serializers.IntegerField()
    trial_type = serializers.ChoiceField(choices=TrialPriceChoices.choices)
    token = serializers.JSONField()
    country_code = serializers.CharField()
    device_session_id = serializers.CharField()
    name = serializers.CharField(allow_blank=True, default="")
    ip = serializers.CharField()


# class PaypalContextRequestSerializer(serializers.Serializer):
#     email = EmailField()
#     subscription_id = serializers.IntegerField()
#     trial_type = serializers.ChoiceField(choices=TrialPriceChoices.choices)
#     name = serializers.CharField()
#     ip = serializers.CharField()


# class PaypalContextResponseSerializer(serializers.Serializer):
#     order_id = serializers.CharField()
#     context_id = serializers.CharField()


# class CheckoutPaypalSerializer(serializers.Serializer):
#     email = EmailField()
#     subscription_id = serializers.IntegerField()
#     context_id = serializers.CharField()


# class CheckoutGooglepaySerializer(serializers.Serializer):
#     signature = serializers.CharField()
#     protocolVersion = serializers.CharField()
#     signedMessage = serializers.CharField()


# class CheckoutGooglepayResponseSerializer(serializers.Serializer):
#     token = serializers.CharField()


class CheckoutPMListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckoutPaymentMethod
        exclude = ['user', 'source_id', 'payment_id', 'fingerprint']
