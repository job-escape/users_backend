
import logging
from typing import Any, Literal, Tuple

from checkout_sdk import exception
from checkout_sdk.checkout_api import CheckoutApi
from checkout_sdk.checkout_sdk import CheckoutSdk
from checkout_sdk.common.common import Address
from checkout_sdk.customers.customers import CustomerRequest
from checkout_sdk.environment import Environment
from checkout_sdk.instruments import instruments
from checkout_sdk.payments import payments
from checkout_sdk.payments.contexts import contexts
from checkout_sdk.tokens import tokens
from django.conf import settings
from rest_framework import status

from account.models import CustomUser, GatewayChoices
from custom.custom_exceptions import BadRequest, InternalServerError
from payment_checkout.models import CheckoutUserSubscription
from subscription.base_api import BaseAPI
from subscription.models import Currency, SubStatusChoices, UserSubscription
from subscription.serializers import UserSubscriptionSerializer
from web_analytics.event_manager import EventManager

logger = logging.getLogger(__name__)
_EVENT_MANAGER = EventManager(GatewayChoices.CHECKOUT)
PAYMENT_REFERENCE = "jobescape_subscription"


class API(BaseAPI):
    system = GatewayChoices.CHECKOUT
    api_secret = settings.CHECKOUT_API_SECRET
    api_public = settings.CHECKOUT_API_KEY
    channel_id = settings.CHECKOUT_CHANNEL_ID
    client: CheckoutApi

    def __init__(self) -> None:
        self.client = CheckoutSdk.builder()\
            .secret_key(self.api_secret)\
            .public_key(self.api_public)\
            .environment(Environment.sandbox() if settings.CHECKOUT_SANDBOX else Environment.production())\
            .build()

    def checkout(
        self,
        amount: float,
        id_or_token: str,
        bool_3ds: bool,
        source_type: Literal['token', 'id'],
        device_id: str,
        country_code: str,
        currency: Currency,
        customer_id: str,
        name: str,
        ip: str,
        user_id: int,
    ) -> Any:
        if source_type == "token":
            source = payments.PaymentRequestTokenSource()
            source.token = id_or_token
            source.type = payments.PaymentSourceType.TOKEN
        else:
            source = payments.RequestCustomerSource()
            source.id = id_or_token
            source.type = payments.PaymentSourceType.ID
        if bool_3ds:
            three_ds = payments.ThreeDsRequest()
            three_ds.enabled = True
            three_ds.challenge_indicator = payments.ChallengeIndicator.NO_CHALLENGE_REQUESTED
            three_ds.attempt_n3d = True
        else:
            three_ds = payments.ThreeDsRequest()
            three_ds.enabled = False
        request = payments.PaymentRequest()
        request.currency = currency  # type: ignore
        request.amount = self.__convent_amount(amount, currency)
        request.payment_type = payments.PaymentType.REGULAR
        request.source = source
        request.processing_channel_id = self.channel_id
        request.three_ds = three_ds
        request.success_url = f"{settings.FRONTEND_FUNNEL_URL}/success"
        request.failure_url = f"{settings.FRONTEND_FUNNEL_URL}/fail"
        risk = payments.RiskRequest()
        risk.enabled = True
        risk.device_session_id = device_id
        request.risk = risk
        customer = payments.PaymentCustomerRequest()
        customer.id = customer_id
        customer.name = name
        request.customer = customer
        address = Address()
        address.country = country_code  # type: ignore
        sender = payments.PaymentIndividualSender()
        sender.address = address
        sender.first_name = "Test"
        sender.last_name = "Test"
        request.sender = sender
        request.payment_ip = ip
        request.reference = PAYMENT_REFERENCE
        request.metadata = {"user_id": user_id}
        try:
            response = self.client.payments.request_payment(request)
        except exception.CheckoutApiException as err:
            if getattr(err, "error_details", ["Unknown error."]) != ['payment_method_not_supported']:
                logger.exception("Checkout: Paywall: CheckoutApiException occured! Error=%s", str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        except exception.CheckoutArgumentException as err:
            logger.exception("Checkout: Paywall: CheckoutArgumentException occured! Error=%s", str(err))
            raise InternalServerError('Checkout argument exception occured.') from err
        return response

    def get_payment_details(self, payment_id) -> Any:
        try:
            response = self.client.payments.get_payment_details(payment_id)
        except exception.CheckoutApiException as err:
            if getattr(err.http_metadata, "status_code") == 404:
                raise BadRequest({"detail": ["Payment not found."]}) from err
            details = getattr(err, "error_details", ["Unknown error."])
            logger.exception("Checkout: Get payment details: CheckoutApiException occured! Error=%s", str(details))
            raise BadRequest({"detail": details}) from err
        return response

    def apple_pay(self, paymentData: dict) -> Any:
        try:
            request = tokens.ApplePayTokenRequest()
            token_data = tokens.ApplePayTokenData()
            token_data.version = paymentData['version']
            token_data.data = paymentData['data']
            token_data.signature = paymentData['signature']
            token_data.header = paymentData['header']
            request.token_data = token_data
            response = self.client.tokens.request_wallet_token(request=request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: ApplePay: CheckoutApiException occured! Error=%s", str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        return response

    def create_instrument(self, token: str, customer_id: str) -> Any:
        request = instruments.CreateTokenInstrumentRequest()
        request.token = token
        customer = instruments.CreateCustomerInstrumentRequest()
        customer.id = customer_id
        request.customer = customer
        try:
            response = self.client.instruments.create(request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: FingerPrint: CheckoutApiException occured! Error=%s", str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        return response

    def check_errors(self, payment_id: str) -> Any:
        """GET payment actions."""
        try:
            response: Any = self.client.payments.get_payment_actions(payment_id)
            response.details = [item.response_summary for item in response.items]
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: 3DS: CheckoutApiException occured! Error=%s", str(getattr(err, "error_details", ["Unknown error."])))
            response.details = ["Unknown error."]
            return response
        return response

    def charge(
        self,
        amount: float,
        payment_id: str,
        source_id: str,
        customer_id: str,
        bool_3ds: bool,
        currency: Currency,
        ip: str,
        user_id: int
    ) -> Any:
        source = payments.PaymentRequestIdSource()
        source.id = source_id
        customer = payments.PaymentCustomerRequest()
        customer.id = customer_id
        request = payments.PaymentRequest()
        request.currency = currency  # type: ignore
        request.amount = self.__convent_amount(amount, currency)
        request.payment_type = payments.PaymentType.RECURRING
        request.source = source
        request.processing_channel_id = self.channel_id
        request.merchant_initiated = True
        request.previous_payment_id = payment_id
        if ip:
            request.payment_ip = ip
        if bool_3ds:
            three_ds = payments.ThreeDsRequest()
            three_ds.enabled = True
            three_ds.attempt_n3d = True
        else:
            three_ds = payments.ThreeDsRequest()
            three_ds.enabled = False
        request.three_ds = three_ds
        request.reference = PAYMENT_REFERENCE
        request.metadata = {"user_id": user_id}
        try:
            response = self.client.payments.request_payment(request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: Reccurring: CheckoutApiException occured! Error=%s", str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        except exception.CheckoutArgumentException as err:
            logger.exception("Checkout: Reccurring: CheckoutArgumentException occured! Error=%s", str(err))
            raise InternalServerError('Checkout argument exception occured.') from err
        return response

    def cancel_subscription(self, user_subscription: UserSubscription) -> Tuple[int, None | dict[str, Any]]:
        # TODO (DEV-123)
        return self.cancel_membership(user_subscription)

    # TODO (DEV-123): divide into different handlers instead and put switch + validation to the gateway
    def cancel_membership(self, user_subscription: UserSubscription) -> Tuple[int, None | dict[str, Any]]:
        """Checkout subscriptions are under our control, so we simply change user subscription status.

        :param user_subscription: concerned user subscription
        :type user_subscription: UserSubscription
        :raises Http404: if resource is not found
        :return: Status code and response data from Solidgate
        :rtype: Tuple[int, None | dict[str, Any]]
        """
        assert user_subscription.user, "?!"
        if user_subscription.status == SubStatusChoices.OVERDUE:
            user_subscription.status = SubStatusChoices.CANCELED
            _EVENT_MANAGER.sendEvent("pr_funnel_subscription_canceled", user_subscription.user.pk, topic="funnel")
        else:
            user_subscription.status = SubStatusChoices.PAUSED
        user_subscription.save()
        return status.HTTP_200_OK, {"user_subscription": UserSubscriptionSerializer(user_subscription).data}

    # TODO (DEV-123): name this resume_all_subscriptions instead and allow to choose which sub-s to resume
    def resume_membership(self, user: CustomUser) -> Tuple[int, None | dict[str, Any]]:
        """Get first PAUSED user subscription. If there are due payments for this subscription, then simply set status to ACTIVE. Otherwise, try charging the user right away, then create next payment attempt and update subscription expiration date if payment was successful. On any error raise BadRequest.

        :param user: concerned user
        :type user: CustomUser
        :return: status 200 if everything went well, 404 if no user subscription was updated and 400 on fail
        :rtype: Tuple[int, None | dict[str, Any]]
        """
        # TODO (DEV-123): handle if multiple user subscriptions found somehow
        user_sub = UserSubscription.objects.filter(user=user, status=SubStatusChoices.PAUSED).select_related('subscription').first()
        if not user_sub or not user_sub.subscription:
            return status.HTTP_404_NOT_FOUND, None
        sub = user_sub.subscription
        currency: Currency = sub.price_currency  # type: ignore
        ch_user_sub = CheckoutUserSubscription.objects.get(user_subscription=user_sub)
        if not ch_user_sub.source_id:
            raise BadRequest("Checkout user subscription does not have source id.")

        # TODO (DEV-123): This does not work as expected. date_due__gte=timezone.now() might exclude attempt prior to now() that is not executed yet due to celerybeat schedule
        # if not CheckoutPaymentAttempt.objects.filter(
        #     date_due__gte=timezone.now(),
        #     ch_user_subscription=ch_user_sub
        # ).exists():
        #     response = self.charge(sub.price_amount, ch_user_sub.payment_id, ch_user_sub.source_id)
        #     if response.status == 'Declined':
        #         logger.warning("Checkout: Resume: Charge was declined for user=%s", user)
        #         raise BadRequest('Payment was declined.')
        #     elif response.status != 'Authorized':
        #         logger.error("Checkout: Recurring: Charge attempt returned status '%s' for user=%s", response.status, user)
        #         raise BadRequest('Payment request returned invalid response.')

        #     date_due = timezone.now() + billing_cycle_to_relativedelta(sub.billing_cycle_frequency, sub.billing_cycle_interval)
        #     CheckoutPaymentAttempt.objects.create(
        #         ch_user_subscription=ch_user_sub,
        #         date_due=date_due
        #     )
        #     user_sub.expires = date_due + EXPIRES_MARGIN

        user_sub.status = SubStatusChoices.ACTIVE
        user_sub.save()

        return status.HTTP_200_OK, None

    def create_customer(self, email: str, name: str, exists=False) -> Any:
        request = CustomerRequest()
        request.email = email
        request.name = name
        try:
            if exists:
                response = self.client.customers.get(email)
            else:
                response = self.client.customers.create(request)
        except exception.CheckoutApiException as err:
            if getattr(err, "error_details", ["Unknown error."]) == ['customer_email_already_exists']:
                return self.create_customer(email, name, exists=True)
            logger.exception("Checkout: Create customer: CheckoutApiException occured! Exists=%s Error=%s",
                             str(exists), str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        return response

    def update_instrument(self, source_id: str, customer_id: str) -> Any:
        customer = instruments.UpdateCustomerRequest()
        customer.id = customer_id
        customer.default = True
        request = instruments.UpdateCardInstrumentRequest()
        request.customer = customer
        try:
            response = self.client.instruments.update(source_id, request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: Update instrument: CheckoutApiException occured! Error=%s",
                             str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        return response

    def create_payment_context(self, amount: float, currency: Currency) -> Any:
        source = contexts.PaymentContextPayPalSource()
        plan = payments.BillingPlan()
        plan.type = payments.BillingPlanType.MERCHANT_INITIATED_BILLING_SINGLE_AGREEMENT
        processing = contexts.PaymentContextsProcessing()
        processing.plan = plan
        # processing.invoice_id = "12345"
        # processing.user_action = contexts.UserAction.PAY_NOW
        item = contexts.PaymentContextsItems()
        item.name = "JobEscape Subscription"
        item.quantity = 1
        item.unit_price = self.__convent_amount(amount, currency)
        item.total_amount = item.unit_price
        request = contexts.PaymentContextsRequest()
        request.source = source
        request.processing_channel_id = self.channel_id
        request.currency = currency  # type: ignore
        request.amount = self.__convent_amount(amount, currency)
        request.capture = True
        request.payment_type = contexts.PaymentType.RECURRING
        # request.payment_type = contexts.PaymentType.REGULAR
        request.processing = processing
        request.items = [item]
        try:
            response = self.client.contexts.create_payment_contexts(request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: Create payment context: CheckoutApiException occured! Error=%s",
                             str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        except exception.CheckoutArgumentException as err:
            logger.exception("Checkout: Create payment context: CheckoutArgumentException occured! Error=%s", str(err))
            raise InternalServerError('Checkout argument exception occured.') from err
        return response

    def get_payment_context(self, context_id: str) -> Any:
        try:
            response = self.client.contexts.get_payment_context_details(context_id)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: Get payment context: CheckoutApiException occured! Error=%s",
                             str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        except exception.CheckoutArgumentException as err:
            logger.exception("Checkout: Get payment context: CheckoutArgumentException occured! Error=%s", str(err))
            raise InternalServerError('Checkout argument exception occured.') from err
        return response

    def checkout_paypal(self, context_id: str, user_id: int) -> Any:
        request = payments.PaymentRequest()
        request.payment_context_id = context_id
        request.processing_channel_id = self.channel_id
        request.reference = PAYMENT_REFERENCE
        request.metadata = {"user_id": user_id}
        try:
            response = self.client.payments.request_payment(request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: PayPal paywall: CheckoutApiException occured! Error=%s",
                             str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        except exception.CheckoutArgumentException as err:
            logger.exception("Checkout: PayPal paywall: CheckoutArgumentException occured! Error=%s", str(err))
            raise InternalServerError('Checkout argument exception occured.') from err
        return response

    def tokenize_google_pay(self, signature: str, protocolVersion: str, signedMessage: str) -> Any:
        request = tokens.GooglePayTokenRequest()
        request.token_data = tokens.GooglePayTokenData()
        request.token_data.signature = signature
        request.token_data.protocolVersion = protocolVersion
        request.token_data.signedMessage = signedMessage
        try:
            response = self.client.tokens.request_wallet_token(request)
        except exception.CheckoutApiException as err:
            logger.exception("Checkout: GooglePay tokenize: CheckoutApiException occured! Error=%s",
                             str(getattr(err, "error_details", ["Unknown error."])))
            raise BadRequest({"detail": getattr(err, "error_details", ["Unknown error."])}) from err
        except exception.CheckoutArgumentException as err:
            logger.exception("Checkout: GooglePay tokenize: CheckoutArgumentException occured! Error=%s", str(err))
            raise InternalServerError('Checkout argument exception occured.') from err
        return response

    def __convent_amount(self, amount: float, currency: Currency):
        # TODO (DEV-124): take into account minor units
        return int(amount*100)  # https://www.checkout.com/docs/payments/accept-payments/calculating-the-amount
