from django.conf import settings
import requests
import requests.auth
import logging
logger = logging.getLogger(__name__)

def createTicket(data: dict):
    url = "https://jobescape.freshdesk.com/api/v2/tickets"
    data = {"name" : data['name'],
            "email": data['email'],
            "subject": 'JobEscape Contact Form',
            "description": data['message'],
            "source": 2,
            "status": 2,
            "priority":2}
    try:
        requests.post(url=url,
                        auth=(requests.auth.HTTPBasicAuth(settings.FRESHDESK_API_KEY, "password")),
                        headers={"Content-Type" : "application/json"},
                        json=data,
                        timeout=settings.REQUESTS_TIMEOUT
                    )
    except requests.exceptions.RequestException as err:  
        logger.exception("Freshdesk Error occured. Error=%s", str(err))