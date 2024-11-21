import base64
import calendar
import hashlib
import hmac
import json
import logging
import uuid

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from growthbook import GrowthBook
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from account.models import CustomUser, GatewayChoices
from custom.custom_backend import SolidgateHeaderAuthentication
from custom.custom_exceptions import BadRequest, InternalServerError
from custom.custom_shortcuts import get_object_or_raise
from payment_solidgate.api import API as SolidgateAPI
from payment_solidgate.api import SOLID_CLIENT
from payment_solidgate.models import (SolidgateSubscription,
                                      SolidgateUserSubscription)
from payment_solidgate.serializers import (
    SolidgateConfirmOrderSerializer, SolidgateDTOSerializer,
    SolidgateOrderUpdatedSerializer, SolidgatePartialDTOSerializer,
    SolidgatePaymentIntentSerializer, SolidgatePaypalInitSerializer,
    SolidgateSubscriptionUpdatedSerializer, SolidgateUpdateIntentSerializer,
    UserForSolidgateSerializer)
from payment_solidgate.utils import (COUNTRY_CODES_MAPPING,
                                     get_partial_payment_intent,
                                     get_payment_intent, get_paypal_init,
                                     get_product_id_from_trial_type,
                                     get_solidgate_subscription_from_sg_sub_id,
                                     map_subscription_id)
from shared.payments import post_purchase
from subscription.models import SubStatusChoices, UserSubscription
from subscription.utils import get_expires_from_subscription
from web_analytics.event_manager import EventManager
from web_analytics.tasks import publishPayment


class SolidgateViewSet(viewsets.GenericViewSet):
    """
        The viewset for performing first payment through Solidgate.
    """
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "payment_intent":
            return SolidgatePaymentIntentSerializer
        if self.action == "update_intent":
            return SolidgateUpdateIntentSerializer
        if self.action == "confirm_order":
            return SolidgateConfirmOrderSerializer
        if self.action == "init_paypal":
            return SolidgatePaypalInitSerializer
        if self.action == "confirm_paypal":
            return SolidgateConfirmOrderSerializer

    @extend_schema(responses={200: SolidgateDTOSerializer})
    @action(methods=['post'], detail=False)
    def payment_intent(self, request: Request):
        try:
            ser = self.get_serializer(data=request.data)
            ser.is_valid(raise_exception=True)
            data = ser.data
            sub_id = data.pop("subscription_id")
            trial_type = data.pop("trial_type")
            email = data.pop("email")
            api = SolidgateAPI()
            user = api.get_checkout_user(email)
            api.check_repeated_checkout(user, sub_id)
            sg_sub = api.get_checkout_subscription(sub_id, SolidgateSubscription)
            product_id = get_product_id_from_trial_type(sg_sub, trial_type)
            data['success_url'] = f"{request._request.headers.get('Origin', settings.FRONTEND_FUNNEL_URL)}/success"
            data['fail_url'] = f"{request._request.headers.get('Origin', settings.FRONTEND_FUNNEL_URL)}/success"
            payment_intent = get_payment_intent(data, user.pk, email, product_id)
            responseDTO = SOLID_CLIENT.form_merchant_data(payment_intent)
            return Response(data={'responseDTO': vars(responseDTO)}, status=status.HTTP_200_OK)
        except Exception as e:
            logging.exception("Solidgate: payment_intent: failed with exception=%s", str(e))
            raise e

    @extend_schema(responses={200: SolidgatePartialDTOSerializer})
    @action(methods=['post'], detail=False)
    def update_intent(self, request: Request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        sub_id = data.pop('subscription_id')
        trial_type = data.pop("trial_type")
        api = SolidgateAPI()
        sg_sub: SolidgateSubscription = api.get_checkout_subscription(sub_id, SolidgateSubscription)
        product_id = get_product_id_from_trial_type(sg_sub, trial_type)
        data['success_url'] = f"{request._request.headers.get('Origin', settings.FRONTEND_FUNNEL_URL)}/success"
        data['fail_url'] = f"{request._request.headers.get('Origin', settings.FRONTEND_FUNNEL_URL)}/success"
        partial_intent = get_partial_payment_intent(data, product_id)
        responseDTO = SOLID_CLIENT.form_update(partial_intent)
        return Response(data={'responseDTO': vars(responseDTO)}, status=status.HTTP_200_OK)

    @extend_schema(responses={200: UserForSolidgateSerializer})
    @action(methods=['post'], detail=False)
    def confirm_order(self, request: Request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        res = SOLID_CLIENT.status({"order_id": ser.data['order_id']})
        data = res.json()
        if res.status_code != status.HTTP_200_OK:
            logging.warning("Solidgate responded with an invalid code on status. Data=%s",
                            json.dumps(data, indent=2))
            EventManager(GatewayChoices.SOLIDGATE).sendPurchaseFailedEvent("Unknown", data, "Solidgate responded with an invalid code on status.")
            return Response(data, res.status_code)
        return self.__handle_success(data, GatewayChoices.SOLIDGATE, request.gb)

    @extend_schema(responses={200: UserForSolidgateSerializer})
    @action(methods=['post'], detail=False)
    def init_paypal(self, request: Request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        sub_id = data.pop("subscription_id")
        trial_type = data.pop("trial_type")
        email = data.pop("email")
        ip = data.pop("ip_address")
        api = SolidgateAPI()
        user = api.get_checkout_user(email)
        api.check_repeated_checkout(user, sub_id)
        sg_sub = api.get_checkout_subscription(sub_id, SolidgateSubscription)
        product_id = get_product_id_from_trial_type(sg_sub, trial_type)
        order_id = str(uuid.uuid4())
        init_data = get_paypal_init(email, ip, order_id, product_id, user.pk)
        body = json.dumps(init_data)
        logging.info("SOLIDGATE: %s", str(body))
        encrypto_data = (settings.SOLIDGATE_API_KEY + body + settings.SOLIDGATE_API_KEY).encode('utf-8')
        sign = hmac.new(settings.SOLIDGATE_API_SECRET.encode('utf-8'), encrypto_data, hashlib.sha512).hexdigest()
        signature = base64.b64encode(sign.encode('utf-8')).decode('utf-8')
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json',
                   'Merchant': settings.SOLIDGATE_API_KEY,
                   'Signature': signature}
        res = requests.post("https://gate.solidgate.com/api/v1/init-payment", headers=headers, json=init_data, timeout=5)
        res_data = res.json()
        logging.info("SOLIDGATE: %s", str(res_data))
        if res_data.get("error"):
            raise BadRequest({"detail": data['error']['messages']})
        script_url = res_data.get("pay_form", {}).get("script_url", "")
        return Response({"script_url": script_url, "order_id": order_id}, res.status_code)

    @extend_schema(responses={200: UserForSolidgateSerializer})
    @action(methods=['post'], detail=False)
    def confirm_paypal(self, request: Request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        body = json.dumps({"order_id": ser.data['order_id']})
        logging.info("SOLIDGATE: %s", str(body))
        encrypto_data = (settings.SOLIDGATE_API_KEY + body + settings.SOLIDGATE_API_KEY).encode('utf-8')
        sign = hmac.new(settings.SOLIDGATE_API_SECRET.encode('utf-8'), encrypto_data, hashlib.sha512).hexdigest()
        signature = base64.b64encode(sign.encode('utf-8')).decode('utf-8')
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json',
                   'Merchant': settings.SOLIDGATE_API_KEY,
                   'Signature': signature}
        res = requests.post("https://gate.solidgate.com/api/v1/status", headers=headers, json={"order_id": ser.data['order_id']}, timeout=5)
        data = res.json()
        if res.status_code != status.HTTP_200_OK:
            logging.warning("Solidgate responded with an invalid code on status. Data=%s",
                            json.dumps(data, indent=2))
            EventManager(GatewayChoices.PAYPAL).sendPurchaseFailedEvent("Unknown", data,
                                                                        "Solidgate responded with an invalid code on status (PayPal).")
            return Response({"detail": data['error']['messages']}, res.status_code)
        return self.__handle_success(data, GatewayChoices.PAYPAL, request.gb)

    def __handle_success(self, data: dict, payment_system: GatewayChoices, gb: GrowthBook):
        """Universal private method for handing successful payments."""
        EVENT_MANAGER = EventManager(payment_system)
        if data.get("error", False):
            raise BadRequest({"detail": data['error']['messages']})
        order_data = data['order']
        if order_data['status'] not in ['auth_ok', 'settle_ok', 'approved', 'void_ok']:
            logging.info("Order with invalid status. Status=%s", order_data['status'])
            EVENT_MANAGER.sendPurchaseFailedEvent("Unknown", data, "Order with invalid status.")
            raise BadRequest("Order with invalid status.")

        user: CustomUser = get_object_or_raise(
            CustomUser.objects.filter(password=''),
            BadRequest("Order does not correspond to any unregistered user."),
            email=order_data['customer_email']
        )

        sg_user_sub_id = order_data['subscription_id']
        if SolidgateUserSubscription.objects.filter(subscription_id=sg_user_sub_id).exists():
            raise BadRequest("Solidgate user subscription already exists.")
        res2 = SolidgateAPI().get_subscription_status(sg_user_sub_id)
        data2 = res2.json()
        if res2.status_code != status.HTTP_200_OK:
            logging.warning("Solidgate responded with an invalid code on subscription. Data=%s",
                            json.dumps(data2, indent=2))
            EVENT_MANAGER.sendPurchaseFailedEvent(user.pk, data2, "Solidgate responded with an invalid code on subscription.")
            return Response(data2, res2.status_code)

        sg_sub_id = data2['product']['id']
        sg_sub = get_solidgate_subscription_from_sg_sub_id(sg_sub_id)
        subscription = sg_sub.subscription
        if not subscription:
            logging.error(
                "Our Subscription matching SolidgateSubscription does not exist! Solidgate subscription id=%d", sg_sub.pk)
            EVENT_MANAGER.sendPurchaseFailedEvent(user.pk, sg_sub.pk, "Our Subscription matching SolidgateSubscription does not exist!")
            raise InternalServerError(f'Our Subscription matching SolidgateSubscription does not exist! Solidgate subscription id={sg_sub.pk}')

        expires = get_expires_from_subscription(subscription)
        _, trans = data['transactions'].popitem()
        card_token = trans['card_token']['token']
        with transaction.atomic():
            # ? Create SolidgateCustomer ?
            user_sub = UserSubscription.objects.create(
                user=user,
                subscription=subscription,
                expires=expires,
                status=SubStatusChoices.TRIALING,
                notification_sent=False,
                paid_counter=1
            )
            SolidgateUserSubscription.objects.create(
                subscription_id=sg_user_sub_id,
                user_subscription=user_sub,
                card_token = card_token
            )
            user.payment_system = payment_system
            if subscription.name == "1Week":
                user.video_credit = 3
                user.video_credit_due = expires
            # user.save() # user.set_register_token() calls .save()
            token = user.set_register_token()

        if trans['operation'] == "apple-pay":
            pm = "solidgate_applepay"
        else:
            pm = "solidgate"
        props = {"payment_method": pm}

        fb_event_id = post_purchase(user, subscription, gb, EVENT_MANAGER, props)
        return Response(data={"token": token, "fb_event_id": fb_event_id}, status=status.HTTP_200_OK)


class SolidgateWebhookViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]  # TODO (DEV-64): ensure authentication and permission
    queryset = None
    authentication_classes = [SolidgateHeaderAuthentication]

    def get_serializer_class(self):
        if self.action == 'subscription_updated':
            return SolidgateSubscriptionUpdatedSerializer
        if self.action == 'order_updated':
            return SolidgateOrderUpdatedSerializer
        return None

    @action(methods=['post'], detail=False, url_path='order/updated')
    def order_updated(self, request: Request):
        """Send payments to BigQuery through PubSub for incoming order events from Solidgate"""
        self.perform_authentication(request)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        logging.info("Solidgate order_updated data=%s", json.dumps(data, indent=2))
        order_data = data['order']
        transaction_data = data['transaction']
        if "card" not in transaction_data and "transactions" in data:  # for successful payments
            _, temp = data['transactions'].popitem()  # type: ignore
            card_data = temp.get("card", {})
        else:
            card_data = transaction_data.get("card", {})
        if "payment_type" not in order_data:
            order_data['payment_type'] = "1-click"
        if order_data['status'] not in ["settle_ok", "approved", "void_ok", "declined", "auth_failed"] or order_data['payment_type'] not in ["1-click", "recurring", "rebill"]:
            # We do not publish such payments
            return Response(status=status.HTTP_204_NO_CONTENT)
        if order_data['order_description'] == "Jobescape upsell":
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            sg_user_sub = SolidgateUserSubscription.objects.select_related('user_subscription__user')\
                .get(subscription_id=order_data['subscription_id'])
            user_sub = sg_user_sub.user_subscription
            if not user_sub.user:
                raise InternalServerError(f'User subscription is not bound to any user! UserSubscription.id={user_sub.pk}')
            user = user_sub.user
            subscription_id = user_sub.subscription_id  # type: ignore
        except SolidgateUserSubscription.DoesNotExist:
            user_sub = None
            user = CustomUser.objects.filter(Q(email=order_data['customer_email']) | Q(payment_email=order_data['customer_email'])).first()
            if user is None:
                logging.warning("Solidgate: order_updated: User not found for email %s", order_data['customer_email'])
                return Response(status=status.HTTP_204_NO_CONTENT)
            subscription_id = map_subscription_id(order_data['amount'])
        payment_method = "applepay" if transaction_data['operation'] == "apple-pay" else "card"
        payment_type = "first" if order_data['payment_type'] == "1-click" else order_data['payment_type']
        order_status = "declined" if order_data['status'] in ["declined", "auth_failed"] else "settled"
        created_at = timezone.datetime.strptime(transaction_data['created_at'], "%Y-%m-%d %H:%M:%S")
        updated_at = timezone.datetime.strptime(transaction_data['updated_at'], "%Y-%m-%d %H:%M:%S")
        months = int(created_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1e6)
        week_date = (created_at - timezone.timedelta(days=created_at.weekday())).date()
        started_at = (calendar.timegm(user_sub.date_started.timetuple()) * 1e6) if user_sub else None
        brand = card_data.get("brand", None)
        if brand is not None:
            brand = brand.capitalize()
        card_country = card_data.get("country", None)
        if card_country is not None:
            card_country = COUNTRY_CODES_MAPPING.get(card_country, "NN")
        publishPayment(settings.PUBSUB_PM_TOPIC_ID, {
            "order_id": order_data['order_id'],
            "status": order_status,
            "amount": order_data['amount'],
            "currency": order_data['currency'],
            "order_description": order_data['order_description'],
            "customer_account_id": user.pk,
            "geo_country": user.funnel_info.get("geolocation", {}).get("country_code", None) if user.funnel_info else None,
            "created_at": int(created_at.timestamp() * 1e6),
            "payment_type": payment_type,
            "settle_datetime": int(updated_at.timestamp() * 1e6),
            "payment_method": payment_method,
            "subscription_id": subscription_id,
            "started_at": started_at,
            "subscription_status": user_sub.status if user_sub else None,
            "card_country": card_country,
            "card_brand": brand,
            "bin": card_data.get("bin", None),
            "gross_amount": order_data['amount'] / 100,
            "week_day": created_at.strftime("%A"),
            "months": months,
            "week_date": week_date,
            "date": created_at.date(),
            "subscription_cohort_date": user_sub.date_started if user_sub else None,
            "mid": order_data.get("mid", "solidgate"),
            "channel": "solidgate",
            "paid_count": user_sub.paid_counter - 1 if user_sub else None,
            "retry_count": None,
            "decline_message": str(transaction_data.get("error", {}).get("recommended_message_for_user", "")) or None,
            "is_3ds": None,
        })
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['post'], detail=False, url_path='subscription/updated')
    def subscription_updated(self, request: Request):
        """Update our user subscriptions based on incoming events from Solidgate"""
        self.perform_authentication(request)
        data: dict = request.data  # type: ignore
        logging.debug("Solidgate subscription_updated data=%s", json.dumps(data, skipkeys=True, indent=2))
        logging.debug("Solidgate callback_type=%s", data['callback_type'])
        match data['callback_type']:
            case 'renew':
                # Solidgate docs: The user has successfully paid for the renewal of the subscription or restored the specific subscription in case it was cancelled.
                return self.__subscription_renewed(data)
            case 'update':
                # Solidgate docs: Support employee cancelled the subscription. OR
                # The subscription goes into the redemption period due to declined recurring payments with retry attempts.
                return self.__subscription_updated(data)
            case 'cancel':
                # Solidgate docs: When a subscription is canceled for any reason, a webhook notification is sent.
                return self.__subscription_canceled(data)
            case 'init':
                # Solidgate docs: The user has successfully started the subscription.
                # Basically, user entered TRIALING. We don't use this
                pass
            case 'resume' | 'pause' | 'pause_schedule.create' | 'pause_schedule.update' | 'pause_schedule.delete':
                # We don't use this
                pass
            case _:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    def __subscription_renewed(self, data: dict):
        """Private handler for `renew` events"""
        subscription_data = data['subscription']
        sg_user_sub = get_object_or_404(SolidgateUserSubscription.objects.select_related(
            'user_subscription__user'), subscription_id=subscription_data['id'])
        user_sub = sg_user_sub.user_subscription
        assert user_sub.user, "Impossible!"
        if not user_sub.subscription:
            raise InternalServerError(f'Solidgate: Webhooks: User subscription is not bound to any subscription! UserSubscription.id={user_sub.pk}')
        user = user_sub.user
        counter = user_sub.paid_counter
        EVENT_MANAGER = EventManager(user.payment_system)  # type: ignore
        EVENT_MANAGER.sendEvent("pr_funnel_recurring_payment", user.pk, {
            'subscription': user_sub.subscription.name,
        }, topic="funnel")
        if counter == 1:
            # subscription.status: trialing -> active
            EVENT_MANAGER.sendEvent("pr_funnel_trial_to_subscription", user.pk, topic="funnel")
        elif counter > 1:
            # subscription.status: canceled -> active or active -> active ( or redemption -> active )
            EVENT_MANAGER.sendEvent("pr_funnel_subscription_renewal", user.pk, {"count": counter}, topic="funnel")
        user_sub.status = SubStatusChoices.ACTIVE
        user_sub.expires = timezone.datetime.strptime(subscription_data['expired_at'], "%Y-%m-%d %H:%M:%S") + timezone.timedelta(days=1)
        user_sub.notification_sent = False
        user_sub.paid_counter = counter + 1
        user_sub.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def __subscription_updated(self, data: dict):
        """Private handler for `update` events"""
        subscription_data = data['subscription']
        if subscription_data['status'] != 'redemption':
            # Support employee cancelled the subscription. Handled by a different webhook event. OR
            # Scheduled to soft cancel. OR
            # Order status changes. Handled by a different webhook event.
            return Response(status=status.HTTP_204_NO_CONTENT)
        sg_user_sub = get_object_or_404(SolidgateUserSubscription.objects.select_related(
            'user_subscription__user'), subscription_id=subscription_data['id'])
        user_sub = sg_user_sub.user_subscription
        assert user_sub.user, "Impossible!"
        user_sub.status = SubStatusChoices.OVERDUE
        # user_sub.expires = subscription_data['expired_at']
        user_sub.save()
        ps: GatewayChoices = user_sub.user.payment_system  # type: ignore
        EventManager(ps).sendEvent("pr_funnel_subscription_past_due", user_sub.user.pk, topic="funnel")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def __subscription_canceled(self, data: dict):
        """Private handler for `cancel` events"""
        subscription_data = data['subscription']
        sg_user_sub = get_object_or_404(SolidgateUserSubscription.objects.select_related(
            'user_subscription__user'), subscription_id=subscription_data['id'])
        user_sub = sg_user_sub.user_subscription
        assert user_sub.user, "Impossible!"
        user_sub.status = SubStatusChoices.CANCELED
        # user_sub.expires = subscription_data['expired_at']
        user_sub.save()
        ps: GatewayChoices = user_sub.user.payment_system  # type: ignore
        EventManager(ps).sendEvent("pr_funnel_subscription_canceled", user_sub.user.pk, topic="funnel")
        return Response(status=status.HTTP_204_NO_CONTENT)
