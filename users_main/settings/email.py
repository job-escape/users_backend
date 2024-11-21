from .core import env, STAGE
import json

if STAGE:
    stage_email_config_json = env("EMAIL_CONFIG")
    prod_email_config_json = None
else:
    stage_email_config_json = None
    prod_email_config_json = env("EMAIL_CONFIG")

stage_email_config = json.loads(stage_email_config_json) if stage_email_config_json else {}
prod_email_config = json.loads(prod_email_config_json) if prod_email_config_json else {}
EMAIL_HOST = stage_email_config.get('EMAIL_HOST') if STAGE else prod_email_config.get("EMAIL_HOST")
EMAIL_PORT = stage_email_config.get('EMAIL_PORT', 587) if STAGE else prod_email_config.get("EMAIL_PORT")
EMAIL_USE_TLS = True
EMAIL_HOST_USER = stage_email_config.get("EMAIL_HOST_USER") if STAGE else prod_email_config.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = stage_email_config.get("EMAIL_HOST_PASSWORD") if STAGE else prod_email_config.get("EMAIL_HOST_PASSWORD")
SERVER_EMAIL = 'support@jobescape.me'
DEFAULT_FROM_EMAIL = 'support@jobescape.me'
ADMINS = [('Admin', 'tech@jobescape.me')]
EMAIL_TIMEOUT = 3
