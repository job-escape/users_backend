import posthog
from django.apps import AppConfig
from django.conf import settings


class WebAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web_analytics'

    def ready(self):
        pass
        # posthog.api_key = settings.POSTHOG_API_KEY
        # posthog.host = settings.POSTHOG_HOST
