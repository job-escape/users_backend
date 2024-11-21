from django.utils.timezone import timedelta

from .core import DEBUG, env

lifetime = timedelta(minutes=1440) if not DEBUG else timedelta(days=30)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": lifetime,
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": env("JWT_SIGNING_KEY"),

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    "TOKEN_OBTAIN_SERIALIZER": "custom.custom_serializers.CustomTokenObtainPairSerializer",
}
