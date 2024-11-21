import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Tuple

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from solidgate import ApiClient

from account.models import CustomUser, GatewayChoices
from payment_solidgate.models import SolidgateUserSubscription
from subscription.base_api import BaseAPI
from subscription.models import SubStatusChoices, UserSubscription

SOLID_CLIENT = ApiClient(settings.SOLIDGATE_API_KEY, settings.SOLIDGATE_API_SECRET)


class API(BaseAPI):
    system = GatewayChoices.SOLIDGATE
    api_secret = settings.SOLIDGATE_API_SECRET
    api_public = settings.SOLIDGATE_API_KEY

    def cancel_subscription(self, user_subscription: UserSubscription) -> Tuple[int, None | dict[str, Any]]:
        # TODO (DEV-123)
        return self.cancel_membership(user_subscription)

    # TODO (DEV-123): divide into different handlers instead and put switch + validation to the gateway
    def cancel_membership(self, user_subscription: UserSubscription) -> Tuple[int, None | dict[str, Any]]:
        """Solidgate does not pause subscriptions indefenitely, therefore we make a cancel request.
        We also cancel immediately if user subscription is past due to avoid retries.

        :param user_subscription: concerned user subscription
        :type user_subscription: UserSubscription
        :raises Http404: if resource is not found
        :return: Status code and response data from Solidgate
        :rtype: Tuple[int, None | dict[str, Any]]
        """
        # https://api-docs.solidgate.com/#tag/Manage-subscriptions/operation/cancelSubscription
        u_s = get_object_or_404(SolidgateUserSubscription, user_subscription=user_subscription)
        subscription_id = u_s.subscription_id
        uri = '/subscription/cancel'
        data = {
            "subscription_id": subscription_id,
            "force": user_subscription.status == SubStatusChoices.OVERDUE,
            "cancel_code": "8.14"  # https://docs.solidgate.com/subscriptions/manage-subscription/subscription-process-overview/#814-cancellation-by-customer
        }
        res = self.__solidgatePost(uri=uri, data=data)
        body = res.json()
        if res.status_code == status.HTTP_200_OK:
            user_subscription.status = SubStatusChoices.PAUSED
            user_subscription.save()
            logging.info("Solidgate: API: Solidgate successfully paused membership! status=%d; body=%s", res.status_code, json.dumps(body, indent=2))
        else:
            logging.warning("Solidgate: API: Solidgate failed to pause membership! status=%d; body=%s", res.status_code, json.dumps(body, indent=2))
        return res.status_code, body

    # TODO (DEV-123): name this resume_all_subscriptions instead and allow to choose which sub-s to resume
    def resume_membership(self, user: CustomUser) -> Tuple[int, None | dict[str, Any]]:
        """Solidgate allows us to restore canceled subscriptions, so that's what we do here for every canceled subscription

        :param user: concerned user
        :type user: CustomUser
        :return: status 200 if everything went well, 404 if no user subscription was updated and 207 otherwise
        :rtype: Tuple[int, None | dict[str, Any]]
        """
        qs = UserSubscription.objects.filter(user=user, status=SubStatusChoices.PAUSED)
        u_s = SolidgateUserSubscription.objects.filter(user_subscription__in=qs).select_related('user_subscription')
        erroneous = None
        for sub in u_s:
            erroneous = erroneous or False
            subscription_id = sub.subscription_id
            uri = '/subscription/restore'
            data = {
                "subscription_id": subscription_id,
                # "expired_at": None
            }
            res = self.__solidgatePost(uri=uri, data=data)
            body = res.json()
            if res.status_code != status.HTTP_200_OK:
                erroneous = True
                logging.error("Solidgate: API: Resume subscription failed! status=%d; body=%s", res.status_code, json.dumps(body, indent=2))
            else:
                sub.user_subscription.status = SubStatusChoices.ACTIVE
                sub.user_subscription.save()
                logging.info("Solidgate: API: Solidgate successfully resumed membership! status=%d; body=%s",
                             res.status_code, json.dumps(body, indent=2))
        if erroneous is None:
            return status.HTTP_404_NOT_FOUND, None
        if erroneous:
            return status.HTTP_207_MULTI_STATUS, None
        return status.HTTP_200_OK, None

    def get_subscription_status(self, subscription_id: str):
        return self.__solidgatePost("/subscription/status", {"subscription_id": subscription_id})

    def __solidgatePost(self, uri: str, data: dict):
        '''`uri` should start from `/`, like `/transactions`'''
        headers = {
            "merchant": self.api_public,
            "signature": self.__generateSignature(self.api_public, json.dumps(data), self.api_secret)
        }
        urn = "https://subscriptions.solidgate.com/api/v1"
        try:
            return requests.post(urn + uri, headers=headers, timeout=settings.REQUESTS_TIMEOUT, json=data)
        except (TimeoutError, requests.Timeout):
            return Response(status=status.HTTP_504_GATEWAY_TIMEOUT)

    def __generateSignature(self, public_key, json_string, secret_key):
        '''Generate encoded hashed signature of the request for sending/receiving requests to/from Solidgate'''
        data = public_key + json_string + public_key
        hmac_hash = hmac.new(secret_key.encode('utf-8'), data.encode('utf-8'), hashlib.sha512).digest()
        return base64.b64encode(hmac_hash.hex().encode('utf-8')).decode('utf-8')
