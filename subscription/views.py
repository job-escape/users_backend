import calendar
import logging
import uuid
import time
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_list_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from payment_solidgate.api import SOLID_CLIENT

from account.models import CustomUser, GatewayChoices
from custom.custom_exceptions import BadRequest
from payment_checkout.api import API as CheckoutAPI
from payment_checkout.models import CheckoutCustomer, CheckoutUserSubscription
from payment_solidgate.models import SolidgateUserSubscription
from payment_solidgate.utils import COUNTRY_CODES_MAPPING
from shared.emailer import send_upsell
from subscription.gateway import PaymentGateway
from subscription.models import (Currency, Subscription, SubscriptionFeedback,
                                 SubStatusChoices, Upsell, UserSubscription,
                                 UserUpsell)
from subscription.serializers import (SubscriptionFeedbackSerializer,
                                      SubscriptionRequestSerializer,
                                      SubscriptionSerializer, UpsellSerializer,
                                      UserSubscriptionSerializer)
from web_analytics.event_manager import EventManager
from web_analytics.tasks import publishPayment

logger = logging.getLogger(__name__)


class UserSubscriptionViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """The viewset for interacting with UserSubscription."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSubscriptionSerializer
    pagination_class = None

    def get_queryset(self):
        return UserSubscription.objects.filter(user=self.request.user)

    @extend_schema(request=inline_serializer('cancel_membership_request_serializer', fields={"comment": serializers.CharField(required=False)}))
    @action(methods=["post"], detail=True)
    def cancel_membership(self, request: Request, pk=None):
        """Pauses or cancels Users's UserSubscription(s) through PaymentGetaway and saves the cancel comment, if any."""
        user: CustomUser = request.user
        if comment := request.data.get("comment", ""):  # type: ignore
            SubscriptionFeedback.objects.create(comment=comment, user=user)
        status_, data = PaymentGateway(user).cancel_membership(comment)
        return Response(data, status_)

    @action(detail=False)
    def last(self, request: Request):
        """Retrieve last UserSubscription."""
        queryset = self.get_queryset()
        last = queryset.order_by("-date_started").first()
        if not last:
            raise NotFound()
        ser = self.get_serializer(last)
        return Response(ser.data)

    # @extend_schema(request=None)
    # @action(methods=["post"], detail=True, permission_classes=[IsAuthenticated])
    # def resume_membership(self, request: Request, pk=None):
    #     """Resumes user's subscription."""
    #     user: CustomUser = request.user
    #     status_, data = PaymentGateway(user).resume_membership()
    #     if status_ == status.HTTP_200_OK:
    #         EventManager(user.payment_system).sendEvent("pr_funnel_subscription_resume", user.pk)  # type: ignore
    #     return Response(data, status_)


class SubscriptionFeedbackViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
        Used by Product Team. Subscription feedbacks.
    """
    queryset = SubscriptionFeedback.objects.all()
    permission_classes = [IsAdminUser]
    serializer_class = SubscriptionFeedbackSerializer


class SubscriptionViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    permission_classes = [AllowAny]
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    pagination_class = None
    filter_backends = []

    @extend_schema(parameters=[SubscriptionRequestSerializer])
    def list(self, request: Request, *args, **kwargs):
        """List available Subscriptions based on the provided currency."""
        if not request.query_params:
            raise BadRequest('Price currency is required in request query parameters.')
        ser = SubscriptionRequestSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        queryset = self.get_queryset()
        queryset = queryset.filter(price_currency=request.query_params['price_currency'])
        ser2 = self.get_serializer(queryset, many=True)
        return Response(ser2.data)


class UpsellViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Upsell.objects.all()
    serializer_class = UpsellSerializer

    @action(detail=True, methods=['post'])
    def purchase(self, request: Request, *args, **kwargs):
        upsell = self.get_object()
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        chase = ser.data['chase']
        user: CustomUser = request.user
        user_sub = get_list_or_404(
            UserSubscription.objects.select_related("subscription"),
            Q(user=user) & ~Q(status=SubStatusChoices.INACTIVE)
        )[-1]
        if not user_sub.subscription:
            logger.warning("Checkout: Upsell: Skipping because UserSubscription is not bound to any Subscription for user email=%s", user.email)
            raise BadRequest("User subscription is not bound to any subscription.")
        if user.payment_system == GatewayChoices.SOLIDGATE:
            return self.__upsell_solidgate(user, upsell, chase, user_sub)
        else:
            return self.__upsell_checkout(user, upsell, chase, user_sub)

    def __upsell_checkout(self, user: CustomUser, upsell: Upsell, chase: bool, user_sub: UserSubscription):
        api = CheckoutAPI()
        EVENT_MANAGER = EventManager(user.payment_system)  # type: ignore
        subscription = user_sub.subscription
        if not CheckoutUserSubscription.objects.filter(user_subscription=user_sub).exists():
            raise BadRequest("Checkout payment method not registered")
        ch_user_sub = CheckoutUserSubscription.objects.get(user_subscription=user_sub)
        payment_id = ch_user_sub.payment_id
        source_id = ch_user_sub.source_id
        if not source_id:
            logger.warning("Checkout: Upsell: Skipping because UserSubscription is not bound to any source_id for payment_id=%s", payment_id)
            raise BadRequest("User has no source id.")
        scheme = ch_user_sub.source_scheme
        if not scheme:
            logger.warning("Checkout: Upsell: Updating card scheme for CheckoutUserSubscription for payment_id=%s", payment_id)
            try:
                response = api.get_payment_details(payment_id)
                scheme = response.source.scheme
                ch_user_sub.source_scheme = scheme
                ch_user_sub.save()
            except Exception as e:
                logger.warning(
                    "Checkout: Upsell: Failed to update card scheme for CheckoutUserSubscription for payment_id=%s due to exception=%s", payment_id, str(e))
        try:
            ch_customer: CheckoutCustomer = user.checkout_customer  # type: ignore
        except CheckoutCustomer.DoesNotExist:
            try:
                response = api.create_customer(user.email, user.full_name)
                ch_customer = CheckoutCustomer.objects.create(id=response.id, user=user)
                api.update_instrument(source_id, ch_customer.id)
            except Exception as e:
                logging.warning(
                    "Checkout: Upsell: Skipping because was unable to create customer or update instrument for payment_id=%s due to exception=%s", payment_id, str(e))
                raise BadRequest("Failed to create customer or update instrument.") from e
        customer_id = ch_customer.id
        three_ds = ch_user_sub.three_ds and scheme == "Mastercard"
        amount = upsell.price_chase_amount if chase else upsell.price_amount
        currency: Currency = upsell.price_currency
        try:
            response = api.charge(
                amount, payment_id, source_id, customer_id,
                three_ds, currency, ch_customer.ip, user.pk
            )
        except Exception as exc:
            logger.exception("Checkout: Upsell for user with email=%s failed due to exception=%s", user.email, str(exc))
        decline_message = None
        if response.status == 'Declined':
            logger.warning("Checkout: Upsell: Charge was declined for user=%s", user.email)
            decline_message = str(response.response_summary)
        elif response.status == 'Authorized':
            UserUpsell.objects.create(
                user=user,
                upsell=upsell,
                paid=True
            )
        else:
            logger.error("Checkout: Upsell: Charge attempt returned status '%s' for user=%s", response.status, user.email)
        if hasattr(response, "requested_on"):
            requested_on = timezone.datetime.strptime(response.requested_on[:-2], "%Y-%m-%dT%H:%M:%S.%f")
        else:
            requested_on = timezone.datetime.strptime(response.processed_on[:-2], "%Y-%m-%dT%H:%M:%S.%f")
        created_at = int(requested_on.timestamp() * 1e6)
        months = int(requested_on.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1e6)
        week_date = (requested_on - timezone.timedelta(days=requested_on.weekday())).date()
        started_at = calendar.timegm(user_sub.date_started.timetuple()) * 1e6
        publishPayment(settings.PUBSUB_PM_TOPIC_ID, {
            "order_id": response.id,
            "status": "settled" if response.status == "Authorized" else "declined",
            "amount": response.amount,
            "currency": response.currency,
            "order_description": "jobescape_upsell",
            "customer_account_id": user.pk,
            "geo_country": user.funnel_info.get("geolocation", {}).get("country_code", None) if user.funnel_info else None,
            "created_at": created_at,
            "payment_type": "upsell",
            "settle_datetime": created_at,
            "payment_method": getattr(response.source, "card_wallet_type", "card"),
            "subscription_id": subscription.pk,
            "started_at": started_at,
            "subscription_status": user_sub.status,
            "card_country": response.source.issuer_country,
            "card_brand": response.source.scheme,
            "gross_amount": response.amount,
            "week_day": requested_on.strftime("%A"),
            "months": months,
            "week_date": week_date,
            "date": requested_on.date(),
            "subscription_cohort_date": requested_on.date(),
            "mid": "checkout",
            "channel": "checkout",
            "paid_count": -2,
            "retry_count": 0,
            "decline_message": decline_message,
            "is_3ds": three_ds,
            "bin": response.source.bin,
        })

        if response.status == 'Authorized':
            if upsell.name == "mentor":
                user.mentor_upsell = True
            else:
                user.prompt_upsell = True
            user.save()
            if upsell.email_bool: 
                send_upsell(user_id=user.pk, email=user.email, template=upsell.template_id)
            EVENT_MANAGER.sendEvent("pr_funnel_upsell_success", user.pk, {'upsell': upsell.name, 'chase': chase}, topic="funnel")
            return Response(status=200)
        else:
            EVENT_MANAGER.sendEvent("pr_funnel_upsell_decline", user.pk, {
                                    'upsell': upsell.name, 'chase': chase, "message": decline_message}, topic="funnel")
            raise BadRequest(decline_message)
        
    def __upsell_solidgate(self, user: CustomUser, upsell: Upsell, chase: bool, user_sub: UserSubscription):
        EVENT_MANAGER = EventManager(user.payment_system)  # type: ignore
        subscription = user_sub.subscription
        if not SolidgateUserSubscription.objects.filter(user_subscription=user_sub).exists():
            raise BadRequest("Solidgate payment method not registered")
        sg_user_sub = SolidgateUserSubscription.objects.get(user_subscription=user_sub)
        card_token = sg_user_sub.card_token
        customer_id = user.pk
        amount = upsell.price_chase_amount if chase else upsell.price_amount
        currency: Currency = upsell.price_currency
        try:
            data = SOLID_CLIENT.recurring({
                "order_id": str(uuid.uuid4()),
                "amount": int(amount*100),
                "currency": currency,
                "order_description": "Jobescape upsell",
                "payment_type": "recurring",
                "recurring_token": card_token,
                "customer_email": user.email,
                "ip_address": user.funnel_info.get("ip", ""),
                "platform": "WEB",
                "customer_account_id": customer_id
            }).json()
        except Exception as exc:
            logger.exception("Solidgate: Upsell for user with email=%s failed due to exception=%s", user.email, str(exc))
        order_data = data['order']
        transaction_data = data['transaction']
        if order_data['status'] == "processing":
            time.sleep(2)
            data = SOLID_CLIENT.status({"order_id": order_data['order_id']}).json()
            if data['order']['status'] == "processing":
                time.sleep(3)
                data = SOLID_CLIENT.status({"order_id": order_data['order_id']}).json()
        order_data = data['order']
        decline_message = str(data.get("error", {}).get("recommended_message_for_user", "Capture"))
        if "card" not in transaction_data and "transactions" in data:  # for successful payments
            _, temp = data['transactions'].popitem()  # type: ignore
            card_data = temp.get("card", {})
        else:
            card_data = transaction_data.get("card", {})
        if "payment_type" not in order_data:
            order_data['payment_type'] = "1-click"
        if order_data['status'] not in ["settle_ok", "approved", "void_ok", "declined", "auth_failed"] or order_data['payment_type'] not in ["1-click", "recurring", "rebill"]:
            raise BadRequest(f"Payment declined {order_data['status']}")
        payment_method = "applepay" if transaction_data['operation'] == "apple-pay" else "card"
        payment_type = "upsell"
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
            "subscription_id": subscription.pk,
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
            "paid_count": -2,
            "retry_count": None,
            "decline_message": decline_message,
            "is_3ds": None,
        })
        if order_status == 'settled':
            if upsell.name == "mentor":
                user.mentor_upsell = True
            else:
                user.prompt_upsell = True
            user.save()
            UserUpsell.objects.create(
                user=user,
                upsell=upsell,
                paid=True
            )
            if upsell.email_bool:
                send_upsell(user_id=user.pk, email=user.email, template=upsell.template_id)
            EVENT_MANAGER.sendEvent("pr_funnel_upsell_success", user.pk, {'upsell': upsell.name, 'chase': chase}, topic="funnel")
            return Response(status=200)
        else:
            EVENT_MANAGER.sendEvent("pr_funnel_upsell_decline", user.pk, {
                                    'upsell': upsell.name, 'chase': chase, "message": decline_message}, topic="funnel")
            raise BadRequest(decline_message)