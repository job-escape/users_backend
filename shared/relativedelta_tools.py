from dateutil.relativedelta import FR, relativedelta
from django.utils import timezone

from subscription.models import BillingCycleIntervals


def billing_cycle_to_relativedelta(frequency: int, interval: str):
    """Converts frequency and interval to a relativedelta that can interact with timezoned datetimes

    :param frequency: Number of intervals
    :type frequency: int
    :param interval: Interval, e.g. 'day', 'week'
    :type interval: str
    :raises ValueError: When interval is not a BillingCycleIntervals type
    :return: timedelta value
    :rtype: relativedelta object
    """
    match interval:
        case BillingCycleIntervals.DAY:
            delta = relativedelta(days=frequency)
        case BillingCycleIntervals.MONTH:
            delta = relativedelta(months=frequency)
        case BillingCycleIntervals.YEAR:
            delta = relativedelta(years=frequency)
        case BillingCycleIntervals.WEEK:
            delta = relativedelta(weeks=frequency)
        case _:
            raise ValueError("Interval is not an acceptable BillingCycleIntervals choice")
    return delta


def next_friday_as_datetime():
    return timezone.now() + relativedelta(days=1, weekday=FR)
