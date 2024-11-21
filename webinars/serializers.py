
from rest_framework import serializers

from webinars.models import Webinar


class WebinarListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webinar
        fields = ['id', 'title', 'hoster', 'status', 'start_datetime', 'duration', 'attendees', 'promo_image']


class WebinarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webinar
        fields = '__all__'


class WebinarRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webinar
        fields = ['status']
