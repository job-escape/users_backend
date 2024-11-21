import logging
from typing import Any

import requests
from checkout_sdk.exception import (CheckoutApiException,
                                    CheckoutAuthorizationException)
from checkout_sdk.workflows.workflows import (CreateWorkflowRequest,
                                              EventWorkflowConditionRequest,
                                              WebhookSignature,
                                              WebhookWorkflowActionRequest)
from django.conf import settings
from django.utils import timezone

from payment_checkout.api import API as CheckoutAPI
from shared.relativedelta_tools import next_friday_as_datetime
from subscription.models import Currency


def billing_retry_calculation(retry: int, amount: float) -> tuple[timezone.datetime, float]:
    """Calculate next billing time and amount based on retry and current amount

    :param retry: Retry count reached so far
    :type retry: int
    :param amount: Amount to bill a user
    :type amount: float
    :return: Next billing datetime and amount, as a tuple
    :rtype: tuple[timezone.datetime, float]
    """
    match retry:
        case 0:
            next_attempt_date = timezone.now() + timezone.timedelta(days=1)
        case 1:
            next_attempt_date = next_friday_as_datetime()
        case 2:
            next_attempt_date = timezone.now() + timezone.timedelta(days=9)
            amount *= 0.75
        case 3:
            next_attempt_date = timezone.now() + timezone.timedelta(days=19)
            amount *= 2/3
        case 4:
            next_attempt_date = timezone.now() + timezone.timedelta(days=1)
            amount *= 0.5
        case _:
            next_attempt_date = timezone.now() + timezone.timedelta(days=1)
    return next_attempt_date, amount


def apple_pay_verification(appleUrl: str, domainName: str):
    """Send request to appleUrl using ApplePay certificates."""
    data = {
        "merchantIdentifier": settings.APPLE_PAY_MERCHANT_ID,
        "domainName": domainName,
        "displayName": "JobEscape"
    }
    cert_file_path = "files/apple_pay/certificate_sandbox.pem"
    key_file_path = "files/apple_pay/certificate_sandbox.key"
    return requests.post(appleUrl, json=data, cert=(cert_file_path, key_file_path))


# Deprecated!
# No longer needed!
def setup_dispute_webhook():
    """
        This script creates a Checkout workflow for a "dispute_created" event webhook.
    """
    api = CheckoutAPI()

    signature = WebhookSignature()
    signature.key = settings.CHECKOUT_WEBHOOK_SECRET
    signature.method = 'HMACSHA256'

    action = WebhookWorkflowActionRequest()
    action.url = 'https://stage.api.jobescape.me/webhooks/checkout/dispute_received' if settings.DEBUG else 'https://api.jobescape.me/webhooks/checkout/dispute_received'
    action.signature = signature

    condition = EventWorkflowConditionRequest()
    condition.events = {"dispute": ['dispute_received']}

    request = CreateWorkflowRequest()
    request.actions = [action]
    request.conditions = [condition]
    request.name = 'Dispute Webhook'
    request.active = True

    try:
        response: Any = api.client.workflows.create_workflow(request)
        workflow_id: str = response.id
        logging.info("Checkout: Webhook setup: Successful. workflow_id=%s", workflow_id)
        return workflow_id
    except CheckoutApiException as err:
        logging.error("Checkout: Webhook setup: Create workflow request failed with response code %d, error_details=%s",
                      err.http_status_code, str(err.error_details))  # type: ignore
    except CheckoutAuthorizationException as err:
        logging.error("Checkout: Webhook setup: Create workflow request authorization failed with response code %d, error_details=%s",
                      err.http_status_code, str(err.error_details))  # type: ignore


def deconvert_amount(amount: int, currency: str) -> float:
    """
        Util to deconvert Checkout int amount to actual float amount.

        Warning: Does not work on all currencies!
    """
    if currency not in Currency:
        raise NotImplementedError("This currency is not supported")
    return amount / 100
