from django.utils.timezone import timedelta

from .core import DEBUG, env, STAGE, stage_jwt_secrets, prod_jwt_secrets

lifetime = timedelta(minutes=1440) if not DEBUG else timedelta(days=30)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": lifetime,
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": stage_jwt_secrets.get("JWT_SIGNING_KEY") if STAGE else prod_jwt_secrets.get("JWT_SIGNING_KEY"),

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    "TOKEN_OBTAIN_SERIALIZER": "custom.custom_serializers.CustomTokenObtainPairSerializer",
}
