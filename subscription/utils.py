from django.utils import timezone

from custom.custom_exceptions import BadRequest
from shared.relativedelta_tools import billing_cycle_to_relativedelta
from subscription.models import Subscription, TrialPriceChoices

EXPIRES_MARGIN = timezone.timedelta(days=1)


def get_expires_from_subscription(subscription: Subscription):
    """Get future expiration date based on the subscription and add `EXPIRES_MARGIN`."""
    interval = subscription.trial_period_interval
    frequency = subscription.trial_cycle_frequency
    delta = billing_cycle_to_relativedelta(frequency, interval)
    return timezone.now() + delta + EXPIRES_MARGIN


def trial_type_to_trial_amount(trial_type: str, subscription: Subscription):
    """Map subscription's trial type to the cost of the trial."""
    match trial_type:
        case TrialPriceChoices.STANDARD:
            return subscription.trial_standard_price_amount
        case TrialPriceChoices.CHASE:
            return subscription.trial_price_chase_amount
        case TrialPriceChoices.TIMEOUT:
            return subscription.trial_timeout_price_amount
        case _:  # Technically impossible to reach this if serializer is correct.
            raise BadRequest("Invalid trial type.")
