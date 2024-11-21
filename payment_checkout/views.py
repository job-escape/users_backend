import logging
from functools import reduce

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from growthbook import GrowthBook
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from account.models import CustomUser, GatewayChoices
from custom.custom_backend import CheckoutHeaderAuthentication
from custom.custom_exceptions import BadRequest
from custom.custom_permissions import HasUnexpiredSubscription
from custom.custom_shortcuts import get_object_or_raise
from payment_checkout.api import API as CheckoutAPI
from payment_checkout.fraud_detection.main import check, check_3ds_codes
from payment_checkout.models import (Checkout3dsPayment, CheckoutCustomer,
                                     CheckoutPaymentAttempt,
                                     CheckoutPaymentMethod,
                                     CheckoutTransaction,
                                     CheckoutUserSubscription,
                                     ChPaymentMethodTypes)
from payment_checkout.serializers import (CheckoutApplePaySerializer,
                                          CheckoutCheckRequestSerializer,
                                          CheckoutPayment3dsSerializer,
                                          CheckoutPaymentRequestSerializer,
                                          CheckoutPaymentResponseSerializer,
                                          CheckoutPMListSerializer,
                                          ValidateApplePaySerializer)
from payment_checkout.utils import apple_pay_verification, deconvert_amount
from shared.payments import post_purchase
from subscription.gateway import PaymentGateway
from subscription.models import (Currency, Subscription, SubStatusChoices,
                                 UserSubscription)
from subscription.utils import (EXPIRES_MARGIN, get_expires_from_subscription,
                                trial_type_to_trial_amount)
from web_analytics.event_manager import EventManager
from web_analytics.tasks import publishPayment

_EVENT_MANAGER = EventManager(GatewayChoices.CHECKOUT)


class CheckoutViewSet(viewsets.GenericViewSet):
    """
        The viewset for performing first payment through Checkout.com.
    """
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'pay':
            return CheckoutPaymentRequestSerializer
        if self.action == 'validate_apple_pay':
            return ValidateApplePaySerializer
        if self.action == 'pay_apple_pay':
            return CheckoutApplePaySerializer
        # if self.action == 'init_paypal':
        #     return PaypalContextRequestSerializer
        # if self.action == 'pay_paypal':
        #     return CheckoutPaypalSerializer
        if self.action == 'check':
            return CheckoutCheckRequestSerializer
        # if self.action == 'init_google_pay':
        #     return CheckoutGooglepaySerializer

    @extend_schema(responses={
        200: CheckoutPaymentResponseSerializer,
        202: CheckoutPayment3dsSerializer
    })
    @action(methods=['post'], detail=False)
    def pay(self, request: Request):
        """
            The view performs all validation and operations necessary for handling a new customer.
        """
        # Validate and extract request data
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        # Check user for repeated checkout
        api = CheckoutAPI()
        user = api.get_checkout_user(data['email'])
        api.check_repeated_checkout(user, data['subscription_id'])
        # Fetch valid subscription based on request data
        subscription = get_object_or_raise(Subscription, BadRequest('Invalid subscription id.'), pk=data['subscription_id'])
        # Fetch or create Checkout Customer
        name = data['name'] or user.full_name
        try:
            ch_customer: CheckoutCustomer = user.checkout_customer  # type: ignore
        except CheckoutCustomer.DoesNotExist:
            response = api.create_customer(user.email, name)
            ch_customer = CheckoutCustomer.objects.create(id=response.id, user=user, ip=data['ip'])  # type: ignore
        # Extract currency and payment amount from the subscription
        currency: Currency = subscription.price_currency
        amount = trial_type_to_trial_amount(data['trial_type'], subscription)
        # Get payment fingerprint from the Checkout for the fraud check
        fingerprint = api.create_instrument(data['token'], ch_customer.id)
        # Carry out fraud check
        fraud, message, fraud_payment = check(
            user_id=user.pk,
            fingerprint=fingerprint.fingerprint,
            email=data['email'],
            ip=data['ip'],
            geo=data['country_code'],
            sub_id=data['subscription_id'],
            trial=data['trial_type'],
            card_bin=fingerprint.bin,
            gb=request.gb
        )
        if fraud == "REJECT":
            raise BadRequest({"detail": message})
        force_3ds = fraud == "FORCE_3DS"
        # Attempt an initial checkout
        response = api.checkout(
            amount, fingerprint.id, force_3ds, "id",
            data['device_session_id'], data['country_code'],
            currency, ch_customer.id, name, data['ip'], user.pk
        )
        # Try 3DS after 2DS only if soft decline was received
        if response.status == 'Declined':
            self.__publish_payment(
                response,
                user,
                subscription,
                "declined",
                None,
                {
                    "decline_message": str(response.response_summary), "is_3ds": force_3ds,
                }
            )
            if not force_3ds and response.response_code in check_3ds_codes:
                # If potential fraud was detected for a user from T1 without 3ds,
                # then skip 3ds and decline immediately
                if response.response_code == "20059" and data['country_code'] not in settings.T1_COUNTRIES:
                    raise BadRequest({"detail": response.response_summary, "bin": response.source.bin})
                # Else attempt second checkout with 3DS
                _EVENT_MANAGER.sendEvent("pr_funnel_3ds_after_2ds", user.pk, {"message": response.response_code}, topic="funnel")
                force_3ds = True
                response = api.checkout(
                    amount, fingerprint.id, force_3ds, "id",
                    data['device_session_id'], data['country_code'],
                    currency, ch_customer.id, name, data['ip'], user.pk
                )
        # If hard decline was received, then return
        if response.status == 'Declined':
            # Update FraudPayment error code and decline
            fraud_payment.error_code = response.response_code
            fraud_payment.save()
            # Publish payment
            self.__publish_payment(
                response,
                user,
                subscription,
                "declined",
                None,
                {
                    "decline_message": str(response.response_summary), "is_3ds": force_3ds,
                }
            )
            raise BadRequest({"detail": response.response_summary, "bin": response.source.bin})
        # If 3DS flow then return redirect url
        if response.status == 'Pending':
            user_sub, _ = UserSubscription.objects.get_or_create(
                user=user,
                subscription=subscription,
                status=SubStatusChoices.INACTIVE
            )
            Checkout3dsPayment.objects.get_or_create(
                id=response.id,
                user_subscription=user_sub,
            )
            return Response({
                "href": response._links.redirect.href,  # pylint: disable=W0212
                "pay_id": response.id
            }, status.HTTP_202_ACCEPTED)
        # response.status == 'Authorized':
        return self.__handle_success(response, subscription, user, request.gb, ChPaymentMethodTypes.CARD)

    @extend_schema(responses={200: CheckoutPaymentResponseSerializer})
    @action(methods=['post'], detail=False)
    def pay_apple_pay(self, request: Request):
        """
            The view performs all validation and operations necessary for handling a new ApplePay customer.
        """
        # Validate and extract request data
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        # Check user for repeated checkout
        api = CheckoutAPI()
        user = api.get_checkout_user(data['email'])
        api.check_repeated_checkout(user, data['subscription_id'])
        # Fetch valid subscription based on request data
        subscription = get_object_or_raise(Subscription, BadRequest('Invalid subscription id.'), pk=data['subscription_id'])
        # Fetch or create Checkout Customer
        name = data['name'] or user.full_name
        try:
            ch_customer: CheckoutCustomer = user.checkout_customer  # type: ignore
        except CheckoutCustomer.DoesNotExist:
            cus_response = api.create_customer(user.email, name)
            ch_customer = CheckoutCustomer.objects.create(id=cus_response.id, user=user, ip=data['ip'])
        # Extract currency and payment amount from the subscription
        currency: Currency = subscription.price_currency
        amount = trial_type_to_trial_amount(data['trial_type'], subscription)
        # Get payment token from the Checkout for initiating a payment
        token = api.apple_pay(data['token']['paymentData'])
        # Attempt a checkout
        pay_response = api.checkout(
            amount, token.token, False, "token",
            data['device_session_id'], data['country_code'],
            currency, ch_customer.id, name, data['ip'], user.pk
        )
        if pay_response.status == 'Declined':
            # Publish payment
            self.__publish_payment(
                pay_response,
                user,
                subscription,
                "declined",
                None,
                {
                    "decline_message": str(pay_response.response_summary), "is_3ds": None,
                    "payment_method": "applepay",
                }
            )
            raise BadRequest({"detail": pay_response.response_summary, "bin": pay_response.source.bin})
        # response.status == 'Authorized':
        return self.__handle_success(pay_response, subscription, user, request.gb, ChPaymentMethodTypes.APPLE_PAY)

    @action(methods=['post'], detail=False)
    def validate_apple_pay(self, request: Request):
        """The view for frontend confirmation."""
        origin = request._request.headers.get("Origin", "")  # pylint: disable=protected-access
        if origin not in settings.CORS_ALLOWED_ORIGINS:
            raise PermissionDenied()
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        response = apple_pay_verification(data['appleUrl'], origin.removeprefix("https://"))
        return Response({"data": response.json()}, status.HTTP_200_OK)

    @extend_schema(responses={
        200: CheckoutPaymentResponseSerializer,
        202: CheckoutPayment3dsSerializer
    })
    @action(methods=['post'], detail=False)
    def check(self, request: Request):
        """The view for 3DS flow on card payments."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.data
        ch_3ds_payment: Checkout3dsPayment = get_object_or_raise(
            Checkout3dsPayment.objects.select_related('user_subscription__user', 'user_subscription__subscription'),
            NotFound('Payment system user subscription not found.'),
            id=data['pay_id']
        )
        user_sub = ch_3ds_payment.user_subscription
        if not (user_sub.user and user_sub.subscription):
            raise BadRequest('User subscription is not bound to a user or a subscription.')
        api = CheckoutAPI()
        det_response = api.get_payment_details(data['pay_id'])
        if det_response.status == 'Declined':
            err_response = api.check_errors(data['pay_id'])
            # Publish payment
            self.__publish_payment(
                det_response,
                user_sub.user,
                user_sub.subscription,
                "declined",
                user_sub,
                {
                    "decline_message": reduce(lambda a, b: a+b+" ", err_response.details, ""),
                    "is_3ds": True,
                }
            )
            raise BadRequest({"detail": err_response.details, "bin": det_response.source.bin})
        if det_response.status == 'Pending':
            return Response({
                "href": det_response._links.redirect.href,  # pylint: disable=W0212
                "pay_id": det_response.id
            }, status.HTTP_202_ACCEPTED)
        # response.status == 'Authorized':
        return self.__handle_success(det_response, user_sub.subscription, user_sub.user, request.gb)

    # @extend_schema(responses={200: PaypalContextResponseSerializer})
    # @action(methods=['post'], detail=False)
    # def init_paypal(self, request: Request):
    #     # Validate and extract request data
    #     ser = self.get_serializer(data=request.data)
    #     ser.is_valid(raise_exception=True)
    #     data = ser.data
    #     # Check user for repeated checkout
    #     api = CheckoutAPI()
    #     user = api.get_checkout_user(data['email'])
    #     api.check_repeated_checkout(user, data['subscription_id'])
    #     # Fetch valid subscription based on request data
    #     subscription = get_object_or_raise(Subscription, BadRequest('Invalid subscription id.'), pk=data['subscription_id'])
    #     try:
    #         ch_customer: CheckoutCustomer = user.checkout_customer  # type: ignore
    #     except CheckoutCustomer.DoesNotExist:
    #         response = api.create_customer(user.email, data['name'])
    #         ch_customer = CheckoutCustomer.objects.create(id=response.id, user=user, ip=data['ip'])  # type: ignore
    #     # Extract currency and payment amount from the subscription
    #     currency: Currency = subscription.price_currency
    #     amount = trial_type_to_trial_amount(data['trial_type'], subscription)
    #     # Get payment context from the Checkout for PayPal
    #     response = api.create_payment_context(amount, currency)
    #     return Response({
    #         "order_id": response.partner_metadata.order_id,
    #         "context_id": response.id
    #     })

    # Deprecated!
    # @extend_schema(responses={200: CheckoutPaymentResponseSerializer})
    # @action(methods=['post'], detail=False)
    # def pay_paypal(self, request: Request):
    #     # Validate and extract request data
    #     ser = self.get_serializer(data=request.data)
    #     ser.is_valid(raise_exception=True)
    #     data = ser.data
    #     api = CheckoutAPI()
    #     # Retrieve user and subscription
    #     user = api.get_checkout_user(data['email'])
    #     subscription = get_object_or_raise(Subscription, BadRequest('Invalid subscription id.'), pk=data['subscription_id'])
    #     # Check payment context status
    #     response = api.get_payment_context(data['context_id'])
    #     if response.status != 'Approved':
    #         raise BadRequest({"detail": ['Payment was not approved.']})
    #     # Attempt a checkout
    #     response2 = api.checkout_paypal(data['context_id'])
    #     if response2.status == 'Declined':
    #         raise BadRequest({"detail": response2.response_summary})
    #     # Set context id to pass to the handler
    #     response2.context_id = data['context_id']
    #     return self.__handle_success(response2, subscription, user, request.gb, GatewayChoices.CHECKOUT_PAYPAL)

    # @extend_schema(responses={200: CheckoutGooglepayResponseSerializer})
    # @action(methods=['post'], detail=False)
    # def init_google_pay(self, request: Request):
    #     # Validate and extract request data
    #     ser = self.get_serializer(data=request.data)
    #     ser.is_valid(raise_exception=True)
    #     data = ser.data
    #     api = CheckoutAPI()
    #     # Tokenize GooglePay data and return
    #     response = api.tokenize_google_pay(
    #         data['signature'], data['protocolVersion'], data['signedMessage']
    #     )
    #     return Response({"token": response.token})

    def __handle_success(self, response, subscription: Subscription, user: CustomUser, gb: GrowthBook, payment_method: ChPaymentMethodTypes = ChPaymentMethodTypes.CARD):
        """Universal private method for handing successful payments."""
        expires = get_expires_from_subscription(subscription)
        us_defaults = {
            "expires": expires,
            "status": SubStatusChoices.TRIALING,
            "paid_counter": 1
        }
        if "source" in dir(response) and "scheme" in dir(response.source):
            scheme = response.source.scheme
        else:
            scheme = "undefined"
        if "3ds" in dir(response):
            obj = getattr(response, "3ds")
            three_ds = getattr(obj, "downgraded", None) is False
        else:
            three_ds = False
        source_id = response.source.id
        with transaction.atomic():
            user_sub, _ = UserSubscription.objects.update_or_create(
                defaults=us_defaults,
                user=user,
                subscription=subscription,
                status=SubStatusChoices.INACTIVE
            )
            ch_method = CheckoutPaymentMethod.objects.create(
                user=user,
                type=payment_method,
                is_selected=True,
                payment_id=response.id,
                source_id=source_id,
                card_scheme=scheme,
                card_last4=response.source.last4,
                card_exp_month=str(response.source.expiry_month),
                card_exp_year=str(response.source.expiry_year),
                fingerprint=response.source.fingerprint,
                three_ds=three_ds,
            )
            ch_user_sub, _ = CheckoutUserSubscription.objects.update_or_create(
                defaults={
                    "source_id": source_id,
                    "payment_id": response.id,
                    "source_scheme": scheme,
                    "three_ds": three_ds,
                    # "customer_id": response.customer.id,
                },
                user_subscription=user_sub,
            )
            if settings.DEBUG:
                date_due = timezone.now() + timezone.timedelta(minutes=5)
            else:
                date_due = expires - EXPIRES_MARGIN
            CheckoutPaymentAttempt.objects.create(
                ch_user_subscription=ch_user_sub,
                user_subscription=user_sub,
                date_due=date_due,
            )
            Checkout3dsPayment.objects.filter(user_subscription=user_sub).delete()
            user.payment_system = GatewayChoices.CHECKOUT
            if subscription.name == "1Week":
                user.video_credit = 3
                user.video_credit_due = expires
            # user.save() # user.set_register_token() calls .save()
            token = user.set_register_token()

        props = {
            "bank_bin": response.source.bin,
            "3ds": three_ds,
            "scheme": scheme,
            "payment_method": payment_method,
        }
        fb_event_id = post_purchase(user, subscription, gb, _EVENT_MANAGER, props)
        self.__publish_payment(
            response,
            user,
            subscription,
            "settled",
            user_sub,
            data={"is_3ds": three_ds}
        )

        return Response({
            "token": token,
            "fb_event_id": fb_event_id
        }, status.HTTP_200_OK)

    def __publish_payment(
        self,
        response, user: CustomUser, subscription: Subscription, res_status: str,
        user_sub: UserSubscription | None = None, data: dict | None = None
    ):
        """Universal private method for publishing payment to BigQuery through PubSub."""
        if hasattr(response, "requested_on"):
            requested_on = timezone.datetime.strptime(response.requested_on[:-2], "%Y-%m-%dT%H:%M:%S.%f")
        else:
            requested_on = timezone.datetime.strptime(response.processed_on[:-2], "%Y-%m-%dT%H:%M:%S.%f")
        created_at = int(requested_on.timestamp() * 1e6)
        months = int(requested_on.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1e6)
        week_date = (requested_on - timezone.timedelta(days=requested_on.weekday())).date()
        d = {
            "order_id": response.id,
            "status": res_status,
            "amount": response.amount,
            "currency": response.currency,
            "order_description": "jobescape_subscription",
            "customer_account_id": user.pk,
            "geo_country": user.funnel_info.get("geolocation", {}).get("country_code", None) if user.funnel_info else None,
            "created_at": created_at,
            "payment_type": "first",
            "settle_datetime": created_at,
            "payment_method": getattr(response.source, "card_wallet_type", "card"),
            "subscription_id": subscription.pk,
            "started_at": created_at,
            "subscription_status": user_sub.status if user_sub else None,
            "card_country": getattr(response.source, "issuer_country", None),
            "card_brand": getattr(response.source, "scheme", None),
            "gross_amount": deconvert_amount(response.amount, response.currency),
            "week_day": requested_on.strftime("%A"),
            "months": months,
            "week_date": week_date,
            "date": requested_on.date(),
            "subscription_cohort_date": requested_on.date(),
            "mid": "checkout",
            "channel": "checkout",
            "paid_count": 0,
            "retry_count": 0,
            "decline_message": None,
            "is_3ds": None,
            "bin": response.source.bin,
        }
        if data:
            d.update(data)
        return publishPayment(settings.PUBSUB_PM_TOPIC_ID, d)


class CheckoutWebhookViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes = [CheckoutHeaderAuthentication]

    @extend_schema(request=inline_serializer("checkout_webhook_serializer", {
        "type": serializers.CharField(default="dispute_received"),
        "data": serializers.JSONField()
    }), responses={200: None})
    @action(methods=['post'], detail=False)
    def dispute_received(self, request: Request):
        data: dict = request.data  # type:ignore
        if data.get("type", None) != "dispute_received":
            raise BadRequest("Invalid event type.")
        payment_id = data['data']['payment_id']
        logging.debug("Checkout: Webhooks: payment_id=%s", payment_id)
        ch_transaction = CheckoutTransaction.objects.select_related('user_subscription__user').get(payment_id=payment_id)
        status_, data_ = PaymentGateway(ch_transaction.user_subscription.user).cancel_membership()
        logging.info("Checkout: Webhooks: dispute cancel subscription response: status=%d, data=%s", status_, str(data_))
        return Response()


class CheckoutPaymentMethodViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.DestroyModelMixin):
    queryset = CheckoutPaymentMethod.objects.all()
    authentication_classes = [HasUnexpiredSubscription]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_serializer_class(self):
        return CheckoutPMListSerializer

    def perform_destroy(self, instance):
        if instance.is_selected:
            raise BadRequest("Deleting default payment method is not allowed.")
        instance.delete()
