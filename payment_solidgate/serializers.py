from rest_framework import serializers

from account.models import CustomUser
from subscription.models import TrialPriceChoices


class SolidgatePaymentIntentSerializer(serializers.Serializer):
    ip_address = serializers.CharField(help_text="8.8.8.8")
    platform = serializers.CharField(default="WEB")
    trial_type = serializers.ChoiceField(choices=TrialPriceChoices.choices)
    subscription_id = serializers.IntegerField()
    geo_country = serializers.CharField(help_text="GBR")
    zip_code = serializers.CharField(help_text="03127")
    email = serializers.CharField(help_text="test@solidgate.com")


class SolidgateUpdateIntentSerializer(serializers.Serializer):
    trial_type = serializers.ChoiceField(choices=TrialPriceChoices.choices)
    subscription_id = serializers.IntegerField()


class SolidgateIntentSerializer(serializers.Serializer):
    payment_intent = serializers.CharField()
    merchant = serializers.CharField()
    signature = serializers.CharField()


class SolidgatePartialIntentSerializer(serializers.Serializer):
    partial_intent = serializers.CharField()
    signature = serializers.CharField()


class SolidgateDTOSerializer(serializers.Serializer):
    responseDTO = SolidgateIntentSerializer()


class SolidgatePartialDTOSerializer(serializers.Serializer):
    responseDTO = SolidgatePartialIntentSerializer()


class UserForSolidgateSerializer(serializers.ModelSerializer):
    fb_event_id = serializers.CharField()

    class Meta:
        model = CustomUser
        fields = ['token', 'fb_event_id']


# class SolidgateConversionsSerializer(serializers.Serializer):
#     gender = serializers.ChoiceField(choices=['m', 'f'], required=False, default='m')
#     client_ip_address = serializers.CharField(required=False, default='')
#     client_user_agent = serializers.CharField(required=False, default='')
#     fbc = serializers.CharField(required=False, default='')
#     city = serializers.CharField(required=False, default='')
#     country_code = serializers.CharField(required=False, default='')
#     zip_code = serializers.CharField(required=False, default='')


class SolidgateConfirmOrderSerializer(serializers.Serializer):
    order_id = serializers.CharField()
    # conversions = SolidgateConversionsSerializer()


class SolidgateSubscriptionUpdatedSerializer(serializers.Serializer):
    callback_type = serializers.CharField()
    invoices = serializers.JSONField()
    customer = serializers.JSONField()
    product = serializers.JSONField()
    subscription = serializers.JSONField()


class SolidgateOrderUpdatedSerializer(serializers.Serializer):
    order = serializers.JSONField()
    transaction = serializers.JSONField()
    transactions = serializers.JSONField()


class SolidgatePaypalInitSerializer(serializers.Serializer):
    email = serializers.CharField()
    ip_address = serializers.CharField()
    trial_type = serializers.ChoiceField(choices=TrialPriceChoices.choices)
    subscription_id = serializers.IntegerField()


# class SolidgateConfirmPayPalSerializer(serializers.Serializer):
#     order_id = serializers.CharField()


class SolidgatePaypalUrlSerializer(serializers.Serializer):
    script_url = serializers.CharField()


# UNUSED SERIALIZERS
# class OrderMetadataSerializer(serializers.Serializer):
#     coupon_code = serializers.CharField(help_text="NY2018")
#     partner_id = serializers.CharField(help_text="123989")


# class BillingAddressSerializer(serializers.Serializer):
#     address = serializers.CharField(help_text="Street 3D, Apartment 343")
#     country = serializers.CharField(help_text="United States")
#     state = serializers.CharField(help_text="Delaware")
#     city = serializers.CharField(help_text="New Castle")
#     zip_code = serializers.CharField(help_text="03127")


# class SolidgateFullPaymentIntentSerializer(serializers.Serializer):
#     ip_address = serializers.CharField(help_text="8.8.8.8", required=True)
#     platform = serializers.CharField(default="WEB", required=True)
#     order_id = serializers.CharField(default=uuid.uuid4(), required=True)
#     order_description = serializers.CharField(default="Jobescape Subscription", required=True)
#     product_id = serializers.CharField(default="fa26d20c-ed5d-4351-9680-3c43a96a60ed", required=True)
#     customer_account_id = serializers.CharField(help_text="4dad42f808", required=True)
#     geo_country = serializers.CharField(help_text="GBR", required=True)
#     customer_email = serializers.CharField(help_text="test@solidgate.com", required=True)
#     language = serializers.CharField(help_text="en", required=False)
#     force3ds = serializers.BooleanField(default=False, required=False)  # type: ignore
#     settle_interval = serializers.IntegerField(default=48, required=False)
#     type = serializers.CharField(help_text="auth", required=False)
#     order_number = serializers.CharField(help_text=1, required=False)
#     order_date = serializers.CharField(help_text="2020-12-21 11:21:30", required=False)
#     order_items = serializers.CharField(help_text="item1, item2", required=False)
#     order_metadata = OrderMetadataSerializer()
#     billing_address = BillingAddressSerializer()
#     device = serializers.CharField(help_text="iPhone 8 iOS 12.0", required=False)
#     user_agent = serializers.CharField(
#         required=False,
#         help_text="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
#     )
#     retry_attempt = serializers.IntegerField(default=1, required=False)
#     geo_city = serializers.CharField(help_text="New Castle", required=False)
#     website = serializers.CharField(help_text="https://google.com", required=False)
#     customer_phone = serializers.CharField(help_text="380111111111", required=False)
#     customer_first_name = serializers.CharField(help_text="John", required=False)
#     customer_last_name = serializers.CharField(help_text="Snow", required=False)
#     customer_date_of_birth = serializers.CharField(help_text="2000-11-21", required=False)
#     success_url = serializers.CharField(help_text="https://merchant.example/success", required=False)
#     fail_url = serializers.CharField(help_text="https://merchant.example/fail", required=False)
#     transaction_source = serializers.CharField(help_text="main_menu", required=False)
#     traffic_source = serializers.CharField(help_text="facebook", required=False)
#     google_pay_merchant_name = serializers.CharField(help_text="Solidgate", required=False)
#     apple_pay_merchant_name = serializers.CharField(help_text="Test", required=False)
