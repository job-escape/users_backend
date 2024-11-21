import logging
from abc import ABC, abstractmethod
from typing import Any, Tuple, TypeVar

from django.shortcuts import get_object_or_404

from account.models import CustomUser
from custom.custom_exceptions import BadRequest, InternalServerError
from custom.custom_shortcuts import get_object_or_raise
# from payment_paddle.models import PaddleSubscription
# from payment_paypal.models import PayPalSubscription
# from payment_rocketgate.models import RocketgateSubscription
from payment_solidgate.models import SolidgateSubscription
# from payment_stripe.models import StripeSubscription
from subscription.models import (Subscription, SubStatusChoices,
                                 UserSubscription)



class BaseAPI(ABC):
    """Base abstract class for payment systems' API"""
    system = None
    """Payment system's name. `None` for BaseAPI"""
    secret = None
    """Payment system's API access token"""

    @abstractmethod
    def cancel_subscription(self, user_subscription: UserSubscription) -> Tuple[int, None | dict[str, Any]]:
        """TODO"""
        raise NotImplementedError()

    @abstractmethod
    def cancel_membership(self, user_subscription: UserSubscription) -> Tuple[int, None | dict[str, Any]]:
        """Pauses membership for a subscriber or cancels subscription(s) for an obligor"""
        raise NotImplementedError()

    @abstractmethod
    def resume_membership(self, user: CustomUser) -> Tuple[int, None | dict[str, Any]]:
        """Resumes membership for a paused subscriber"""
        raise NotImplementedError()

    def get_checkout_user(self, email: str) -> CustomUser:
        user = get_object_or_404(CustomUser.objects.select_related('checkout_customer'), email=email)
        if user.password != "":
            raise BadRequest("User is already registered.")
        return user

    def get_checkout_subscription(self, subscription_id: int, klass: type[SolidgateSubscription]) -> SolidgateSubscription:
        try:  # TODO (DEV-123): refactor and make as one db query
            subscription = get_object_or_raise(
                Subscription,
                BadRequest('Invalid subscription id.'),
                id=subscription_id
            )
            return klass.objects.get(subscription=subscription)
        except klass.DoesNotExist as exc:
            logging.error("%s subscription matching our subscription does not exist! Our subscription id=%d",
                          self.system, subscription_id)
            raise InternalServerError(f"{self.system} subscription matching our subscription does not exist!") from exc

    def check_repeated_checkout(self, user: CustomUser, subscription_id: int, raise_exception=True):
        """Check if there's a UserSubscription that is not inactive for that user"""
        if UserSubscription.objects.filter(user=user).exclude(status=SubStatusChoices.INACTIVE).exists():
            if raise_exception:
                raise BadRequest("Repeated checkout is not allowed (there's already a user subscription).")
            return False
        return True

    def __str__(self) -> str:
        return f"API ({self.system})"
