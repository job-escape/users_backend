import os

from django.utils import timezone

from .core import (
    BASE_DIR, DEBUG, STAGE, env, 
    stage_solidgate_config, 
    prod_solidgate_config, 
    stage_posthog_config, 
    prod_posthog_config,
    stage_checkout_config,
    prod_checkout_config,
    stage_conversions_config,
    prod_conversions_config,
    stage_pubsub_config,
    prod_pubsub_config,
    stage_users_tasks,
    prod_users_tasks,
    gcp_infos,
)

# CONSTANTS
T1_COUNTRIES = ["AE", "AT", "AU", "BH", "BN", "CA", "CZ", "DE", "DK", "ES", "FI", "FR", "GB",
                "HK", "IE", "IL", "IT", "JP", "KR", "NL", "NO", "PT", "QA", "SA", "SE", "SG", "SI", "US", "NZ"]


# DJANGO ADDITIONAL SETTINGS
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
# DEFAULT_EXCEPTION_REPORTER = 'custom.custom_exception_handler.CustomExceptionReporter'

# APP SETTINGS
REQUESTS_TIMEOUT = 10  # seconds
PASSWORD_TOKEN_EXPIRATION_DELTA = timezone.timedelta(hours=1)  # Timedelta before which password reset code set on user is considered valid
REGISTRATION_TOKEN_EXPIRATION_DELTA = timezone.timedelta(days=30)  # Timedelta before which registration token is considered valid
if DEBUG and not STAGE:
    FRONTEND_FUNNEL_URL = 'http://localhost'
else:
    FRONTEND_FUNNEL_URL = env("FRONTEND_FUNNEL_URL", str)


# MAILERLITE EMAILER
MAILERLITE_API_KEY = env("MAILERLITE_API_KEY")

# POSTMARK EMAILER
PM_API_SECRET = env('PM_API_SECRET')

# AMPLITUDE ANALYTICS
AMPLITUDE_API_KEY = env('AMPLITUDE_API_KEY')
# AMPLITUDE_API_SECRET = env('AMPLITUDE_API_SECRET')


# META CONVERSIONS API
CONVERSIONS_PIXEL_ID = stage_conversions_config.get("CONVERSIONS_PIXEL_ID") if STAGE else prod_conversions_config.get("CONVERSIONS_PIXEL_ID")
CONVERSIONS_SECRET = stage_conversions_config.get("CONVERSIONS_SECRET") if STAGE else prod_conversions_config.get("CONVERSIONS_SECRET")


# POSTHOG ANALYTICS
POSTHOG_API_KEY = stage_posthog_config.get('POSTHOG_API_KEY') if STAGE else prod_posthog_config.get('POSTHOG_API_KEY')
POSTHOG_HOST = stage_posthog_config.get('POSTHOG_HOST') if STAGE else prod_posthog_config.get('POSTHOG_HOST')


# SOLIDGATE
SOLIDGATE_API_KEY = stage_solidgate_config.get('SOLIDGATE_API_KEY') if STAGE else prod_solidgate_config.get('SOLIDGATE_API_KEY')
SOLIDGATE_API_SECRET = stage_solidgate_config.get('SOLIDGATE_API_SECRET') if STAGE else prod_solidgate_config.get('SOLIDGATE_API_SECRET')
SOLIDGATE_WEBHOOK_KEY = stage_solidgate_config.get('SOLIDGATE_WEBHOOK_KEY') if STAGE else prod_solidgate_config.get('SOLIDGATE_WEBHOOK_KEY')
SOLIDGATE_WEBHOOK_SECRET = stage_solidgate_config.get('SOLIDGATE_WEBHOOK_SECRET') if STAGE else prod_solidgate_config.get('SOLIDGATE_WEBHOOK_SECRET')


# CHECKOUT
CHECKOUT_SANDBOX = stage_checkout_config.get("CHECKOUT_ENVIRONMENT") if STAGE else prod_checkout_config.get("CHECKOUT_ENVIRONMENT")
CHECKOUT_API_KEY = stage_checkout_config.get("CHEKCOUT_API_KEY") if STAGE else prod_checkout_config.get("CHECKOUT_API_KEY")
CHECKOUT_API_SECRET = stage_checkout_config.get("CHECKOUT_API_SECRET") if STAGE else prod_checkout_config.get("CHECKOUT_API_SECRET")
CHECKOUT_CHANNEL_ID = stage_checkout_config.get("CHECKOUT_CHANNEL_ID") if STAGE else prod_checkout_config.get("CHECKOUT_CHANNEL_ID")
CHECKOUT_WEBHOOK_SECRET = stage_checkout_config.get("CHECKOUT_WEBHOOK_SECRET") if STAGE else prod_checkout_config.get("CHECKOUT_WEBHOOK_SECRET")
CHECKOUT_WEBHOOK_AUTH = stage_checkout_config.get("CHECKOUT_WEBHOOK_AUTH") if STAGE else prod_checkout_config.get("CHECKOUT_WEBHOOK_AUTH")
APPLE_PAY_MERCHANT_ID = stage_checkout_config.get("APPLE_PAY_MERCHANT_ID") if STAGE else prod_checkout_config.get("APPLE_PAY_MERCHANT_ID")

# TELEGRAM BOT
TELEGRAM_BOT_TOKEN = env('TELEGRAM_BOT_TOKEN')


# FRESHDESK
FRESHDESK_API_KEY = env('FRESHDESK_API_KEY')


# GOOGLE CLOUD AND PUBSUB
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(BASE_DIR, "files/pubsub.secret.json")
PUBSUB_PROJECT_ID = stage_pubsub_config.get("PUBSUB_PROJECT_ID") if STAGE else prod_pubsub_config.get("PUBSUB_PROJECT_ID")
PUBSUB_APP_TOPIC_ID = stage_pubsub_config.get("PUBSUB_APP_TOPIC_ID") if STAGE else prod_pubsub_config.get("PUBSUB_APP_TOPIC_ID")
PUBSUB_FUNNEL_TOPIC_ID = stage_pubsub_config.get("PUBSUB_FUNNEL_TOPIC_ID") if STAGE else prod_pubsub_config.get("PUBSUB_FUNNEL_TOPIC_ID")
PUBSUB_UDID_TOPIC_ID = stage_pubsub_config.get("PUBSUB_UDID_TOPIC_ID") if STAGE else prod_pubsub_config.get("PUBSUB_UDID_TOPIC_ID")
PUBSUB_PM_TOPIC_ID = stage_pubsub_config.get("PUBSUB_PM_TOPIC_ID") if STAGE else prod_pubsub_config.get("PUBSUB_PM_TOPIC_ID")


# GCP INFOS
GCP_PROJECT_ID = gcp_infos.get("GCP_PROJECT_ID")
GCP_LOCATION = gcp_infos.get("GCP_LOCATION")

# USERS URL
PROD_USERS_SERVICE_URL = "https://api.user.jobescape.me"
STAGE_USERS_SERVICE_URL = env("STAGE_USERS_SERVICE_URL") # "https://stage.api.user.jobescape.me"

# GOOGLE TASKS INFO
STAGE_QUEUE_SEND_WELCOME = stage_users_tasks.get('STAGE_QUEUE_SEND_WELCOME') if STAGE else prod_users_tasks.get("PROD_QUEUE_SEND_WELCOME")
STAGE_QUEUE_DELAY_EMAIL=stage_users_tasks.get('STAGE_QUEUE_DELAY_EMAIL') if STAGE else prod_users_tasks.get("PROD_QUEUE_DELAY_EMAIL")
STAGE_QUEUE_FAREWELL_EMAIL=stage_users_tasks.get('STAGE_QUEUE_FAREWELL_EMAIL') if STAGE else prod_users_tasks.get("PROD_QUEUE_FAREWELL_EMAIL")
STAGE_QUEUE_CLOUD_EVENT=stage_users_tasks.get('STAGE_QUEUE_CLOUD_EVENT') if STAGE else prod_users_tasks.get("PROD_QUEUE_CLOUD_EVENT")
STAGE_QUEUE_PUBLISH_PAYMENT=stage_users_tasks.get('STAGE_QUEUE_PUBLISH_PAYMENT') if STAGE else prod_users_tasks.get("PROD_QUEUE_PUBLISH_PAYMENT")
STAGE_QUEUE_PUBLISH_EVENT=stage_users_tasks.get('STAGE_QUEUE_PUBLISH_EVENT') if STAGE else prod_users_tasks.get("PROD_QUEUE_PUBLISH_EVENT")
STAGE_QUEUE_BIND_DEVICE=stage_users_tasks.get('STAGE_QUEUE_BIND_DEVICE') if STAGE else prod_users_tasks.get("PROD_QUEUE_BIND_DEVICE")


# MICROSERVICE URLS
ACADEMY_SERVICE_URL=env("ACADEMY_SERVICE_URL")
AI_SERVICE_URL=env("AI_SERVICE_URL")