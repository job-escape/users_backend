
import os

from django.utils.translation.trans_null import gettext_lazy as _
from rest_framework import status

from account.models import CustomUser, GatewayChoices
from payment_checkout.api import API as Checkout
# from payment_paddle.api import API as Paddle
# from payment_paypal.api import API as Paypal
# from payment_paytabs.api import API as Paytabs
# from payment_rocketgate.api import API as Rocketgate
from payment_solidgate.api import API as Solidgate
from shared.emailer import send_farewell_email
from subscription.base_api import BaseAPI
from subscription.models import SubStatusChoices, UserSubscription
from web_analytics.event_manager import EventManager
from google_tasks.tasks import create_send_farewell_email_task

class PaymentGateway:
    mapping = {  # TODO (DEV-121): remove APPLE_PAY, GOOGLE_PAY, CHECKOUT_PAYPAL, PADDLE
        # GatewayChoices.PADDLE: Paddle,
        # GatewayChoices.PAYTABS: Paytabs,
        GatewayChoices.SOLIDGATE: Solidgate,
        # GatewayChoices.PAYPAL: Solidgate,
        # GatewayChoices.ROCKETGATE: Rocketgate,
        GatewayChoices.CHECKOUT: Checkout,
        # GatewayChoices.APPLE_PAY: Checkout,
        # GatewayChoices.CHECKOUT_PAYPAL: Checkout,
        # GatewayChoices.GOOGLE_PAY: Checkout
        # 1: None
    }
    """Mapping GatewayChoices to the payment system APIs"""
    user: CustomUser
    api: BaseAPI
    """User's payment system API"""

    def __init__(self, user) -> None:
        assert isinstance(user, CustomUser), 'User must be a CustomUser instance'
        self.user = user
        api = self.mapping.get(user.payment_system)  # type: ignore
        assert api, 'Undefined payment system for user'
        self.api = api()

    def cancel_membership(self, comment=None):
        """Pauses membership for a subscriber or cancels subscription(s) for an obligor"""
        if user_subscription := UserSubscription.objects.filter(user=self.user).exclude(status=SubStatusChoices.CANCELED).select_related('user', 'subscription').first():
            if user_subscription.status == SubStatusChoices.TRIALING:
                sub_status = "trial"
            else:
                sub_status = "subscription"
            status_, data = self.api.cancel_membership(user_subscription)
            if status_ == status.HTTP_200_OK:
                EventManager(self.user.payment_system).sendEvent(  # type: ignore
                    "pr_webapp_unsubscribed", self.user.pk, {"unsubscribe_reason": comment},
                    topic="app"
                )
                fmt = "%b %-d, %Y"
                fmt = fmt.replace('%-', '%#') if os.name == 'nt' else fmt
                create_send_farewell_email_task(
                    self.user.pk,
                    self.user.email,
                    self.user.full_name,
                    sub_status,
                    user_subscription.expires.strftime(fmt),
                    user_subscription.subscription.name if user_subscription.subscription else 'prior'
                )
                # send_farewell_email.delay(
                #     self.user.pk,
                #     self.user.email,
                #     self.user.full_name,
                #     sub_status,
                #     user_subscription.expires.strftime(fmt),
                #     user_subscription.subscription.name if user_subscription.subscription else 'prior'
                # )
            return status_, data
        else:
            return status.HTTP_400_BAD_REQUEST, {"detail": "User does not have any non-canceled subscriptions"}

    def resume_membership(self):
        """Resumes membership for a paused subscriber"""
        # TODO (DEV-123): Refactor
        if user_subscription := UserSubscription.objects.filter(user=self.user, status=SubStatusChoices.PAUSED).first():
            return self.api.resume_membership(self.user)
        else:
            return status.HTTP_400_BAD_REQUEST, {"detail": "User does not have any paused subscriptions"}

    def __str__(self) -> str:
        return f'PaymentGateway for user={self.user}, api={self.api}'
