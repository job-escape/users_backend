import datetime
import json
import uuid

from django.utils import timezone
from rest_framework import serializers


class PubsubSerializer(serializers.Serializer):

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        fields = self._readable_fields
        for field in fields:
            if isinstance(field, serializers.DictField):
                dictionary = representation.get(field.field_name, None)
                if dictionary:
                    for key, value in dictionary.items():
                        if isinstance(value, datetime.datetime):
                            dictionary[key] = value.timestamp()
                    representation[field.field_name] = json.dumps(dictionary)
        return representation


# ? using serializer with Celery tasks yields same timestamp and creates same uuid4 for multiple users sometimes
class EventRawSerializer(PubsubSerializer):
    event_id = serializers.UUIDField(default=uuid.uuid4)
    device_id = serializers.CharField()
    user_id = serializers.CharField(allow_null=True, required=False)
    event_name = serializers.CharField()
    timestamp = serializers.IntegerField(default=round(timezone.now().timestamp() * 1e6))
    path = serializers.CharField(allow_blank=True)
    ip = serializers.CharField(allow_null=True, required=False)
    user_agent = serializers.CharField(allow_null=True, required=False)
    referrer = serializers.CharField(allow_null=True, required=False)
    language = serializers.CharField(allow_null=True, required=False)
    country_code = serializers.CharField(allow_null=True, required=False)
    country = serializers.CharField(allow_null=True, required=False)
    city = serializers.CharField(allow_null=True, required=False)
    region = serializers.CharField(allow_null=True, required=False)
    attribution_id = serializers.CharField(allow_null=True, required=False)
    event_metadata = serializers.DictField(allow_null=True, required=False)
    user_metadata = serializers.DictField(allow_null=True, required=False)
    query_parameters = serializers.DictField(allow_null=True, required=False)


class PaymentsSerializer(PubsubSerializer):
    order_id = serializers.CharField(allow_null=True, required=False)
    status = serializers.CharField(allow_null=True, required=False)
    amount = serializers.IntegerField(allow_null=True, required=False)
    currency = serializers.CharField(allow_null=True, required=False)
    order_description = serializers.CharField(allow_null=True, required=False)
    customer_account_id = serializers.CharField(allow_null=True, required=False)
    geo_country = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.IntegerField(allow_null=True, required=False)
    payment_type = serializers.CharField(allow_null=True, required=False)
    settle_datetime = serializers.IntegerField(allow_null=True, required=False)
    # refund_datetime = serializers.CharField(allow_null=True, required=False)
    payment_method = serializers.CharField(allow_null=True, required=False)
    subscription_id = serializers.CharField(allow_null=True, required=False)
    started_at = serializers.IntegerField(allow_null=True, required=False)
    # cancelled_at = serializers.IntegerField(allow_null=True, required=False)
    subscription_status = serializers.CharField(allow_null=True, required=False)
    # retry_attempt = serializers.CharField(allow_null=True, required=False)
    card_country = serializers.CharField(allow_null=True, required=False)
    card_brand = serializers.CharField(allow_null=True, required=False)
    gross_amount = serializers.FloatField(allow_null=True, required=False)
    week_day = serializers.CharField(allow_null=True, required=False)
    months = serializers.IntegerField(allow_null=True, required=False)
    week_date = serializers.DateField(allow_null=True, required=False)
    date = serializers.DateField(allow_null=True, required=False)
    subscription_cohort_date = serializers.DateField(allow_null=True, required=False)
    # attempt_date_0 = serializers.CharField(allow_null=True, required=False)
    # attempt_date_1 = serializers.CharField(allow_null=True, required=False)
    # attempt_date_2 = serializers.CharField(allow_null=True, required=False)
    # attempt_date_3 = serializers.CharField(allow_null=True, required=False)
    # attempt_date_4 = serializers.CharField(allow_null=True, required=False)
    mid = serializers.CharField(allow_null=True, required=False)
    channel = serializers.CharField(allow_null=True, required=False)
    paid_count = serializers.IntegerField(allow_null=True, required=False)
    retry_count = serializers.IntegerField(allow_null=True, required=False)
    decline_message = serializers.CharField(allow_null=True, required=False)
    is_3ds = serializers.BooleanField(allow_null=True, required=False)
    bin = serializers.CharField(allow_null=True, required=False)
