import calendar
import logging

from django.conf import settings
from django.utils import timezone

from payment_checkout.api import API as CheckoutAPI
from payment_checkout.models import (CheckoutCustomer, CheckoutPaymentAttempt,
                                     CheckoutPaymentMethod,
                                     CheckoutTransaction)
from payment_checkout.utils import billing_retry_calculation, deconvert_amount
from shared.relativedelta_tools import billing_cycle_to_relativedelta
from subscription.models import Currency, SubStatusChoices, UserSubscription
from subscription.utils import EXPIRES_MARGIN
from web_analytics.event_manager import EventManager
from web_analytics.tasks import publishPayment

logger = logging.getLogger(__name__)

HARD_DECLINE_CODES = [
    "30004", "30007", "30015", "30016", "30017", "30018", "30019",
    "30020", "30021", "30022", "30033", "30034", "30035", "30036",
    "30037", "30038", "30041", "30043", "30044", "30045", "30046",
    "40101", "40201", "40202", "40203", "40204", "40205", "50002",
    "50003", "20183", "20182", "20179", "20059",
]


def attempt_error_fallback(attempt: CheckoutPaymentAttempt, msg: str):
    attempt.response_summary = msg
    attempt.executed = True
    attempt.save()


def user_sub_error_fallback(user_sub: UserSubscription, status: SubStatusChoices):
    user_sub.status = status
    user_sub.save()


# @app.task(ignore_result=True)
def run_charge_users():
    """
        Charges all Checkout subscribers based on CheckoutPaymentAttemp with `date_due < timezone.now()` and updates UserSubscriptions.
        Also creates corresponding CheckoutPaymentAttemps for successful payments or retries.
    """
    # Fetch all due payment attempts
    queryset = CheckoutPaymentAttempt.objects.filter(executed=False, date_due__lt=timezone.now())\
        .select_related("ch_user_subscription__user_subscription__user__checkout_customer")\
        .prefetch_related("ch_user_subscription__user_subscription__subscription")
    api = CheckoutAPI()
    updated_attempts_count = 0
    user_subs_count = 0
    for attempt in queryset:
        ch_user_sub = attempt.ch_user_subscription
        assert ch_user_sub
        payment_id = ch_user_sub.payment_id
        source_id = ch_user_sub.source_id
        user_sub = ch_user_sub.user_subscription
        if user_sub.status not in [SubStatusChoices.ACTIVE, SubStatusChoices.TRIALING, SubStatusChoices.OVERDUE]:
            logger.debug("Checkout: Recurring: Skipping because UserSubscription has inappropriate status=%s", user_sub.status)
            attempt_error_fallback(attempt, "Inappropriate UserSubscription status")
            updated_attempts_count += 1
            continue
        sub = user_sub.subscription
        if not sub:
            logger.warning("Checkout: Recurring: Skipping because UserSubscription is not bound to any Subscription for attempt=%s", attempt)
            attempt_error_fallback(attempt, "No Subscription on UserSubscription")
            updated_attempts_count += 1
            continue
        if not source_id:
            logger.warning("Checkout: Recurring: Skipping because UserSubscription is not bound to any source_id for attempt=%s", attempt)
            continue
        user = user_sub.user
        if not user:
            logger.warning("Checkout: Recurring: Skipping because UserSubscription is not bound to any CustomUser for attempt=%s", attempt)
            attempt_error_fallback(attempt, "No CustomUser on UserSubscription")
            updated_attempts_count += 1
            continue
        if not user.password:
            logging.warning("Checkout: Recurring: Subscription was cancelled because CustomUser has no password for attempt=%s", attempt)
            user_sub_error_fallback(user_sub, SubStatusChoices.CANCELED)
            user_subs_count += 1
            attempt_error_fallback(attempt, "Empty password on CustomUser")
            updated_attempts_count += 1
            continue
        scheme = ch_user_sub.source_scheme
        if not scheme:
            logger.warning("Checkout: Recurring: Updating card scheme for CheckoutUserSubscription for attempt=%s", attempt)
            try:
                response = api.get_payment_details(payment_id)
                scheme = response.source.scheme
                ch_user_sub.source_scheme = scheme
                ch_user_sub.save()
            except Exception as e:
                logger.warning(
                    "Checkout: Recurring: Failed to update card scheme for CheckoutUserSubscription for attempt=%s due to exception=%s", attempt, str(e))
        try:
            ch_customer: CheckoutCustomer = user.checkout_customer  # type: ignore
        except CheckoutCustomer.DoesNotExist:
            try:
                response = api.create_customer(user.email, user.full_name)
                ch_customer = CheckoutCustomer.objects.create(id=response.id, user=user)
                api.update_instrument(source_id, ch_customer.id)
            except Exception as e:
                logging.warning(
                    "Checkout: Recurring: Skipping because was unable to create customer or update instrument for attempt=%s due to exception=%s", attempt, str(e))
                continue
        customer_id = ch_customer.id
        three_ds = ch_user_sub.three_ds and scheme == "Mastercard"
        amount = sub.price_amount
        currency: Currency = sub.price_currency  # type: ignore
        next_attempt_date, amount = billing_retry_calculation(attempt.retry, amount)
        EVENT_MANAGER = EventManager(user.payment_system)  # type: ignore
        # Event flags to send at the end
        flag_t_to_s = False
        flag_renewal = False

        try:
            response = api.charge(
                amount, payment_id, source_id, customer_id,
                three_ds, currency, ch_customer.ip, user.pk
            )
        except Exception as exc:
            logger.exception("Checkout: Recurring: Skipping attempt_id=%d due to exception=%s", attempt.pk, str(exc))
            continue
        # Immediately save executed attempt
        attempt.response = response.status
        attempt.response_code = response.response_code
        attempt.response_summary = getattr(response, "response_summary", "")
        attempt.executed = True
        attempt.save()
        updated_attempts_count += 1
        # Handle responses
        decline_message = None
        counter = user_sub.paid_counter
        if response.status == 'Declined':
            logger.warning("Checkout: Recurring: Charge was declined for attempt=%s", attempt)
            decline_message = str(response.response_summary)
            if response.response_code in HARD_DECLINE_CODES:
                logger.info("Checkout: Recurring: Subscription was cancelled due to response code=%s", response.response_code)
                user_sub_error_fallback(user_sub, SubStatusChoices.CANCELED)
                user_subs_count += 1
            elif attempt.retry >= 4:
                logger.info("Checkout: Recurring: Subscription was cancelled after 4th retry for user_sub=%s", user_sub)
                user_sub_error_fallback(user_sub, SubStatusChoices.CANCELED)
                user_subs_count += 1
            else:
                if settings.DEBUG:
                    next_date_due = timezone.now() + timezone.timedelta(minutes=5)
                else:
                    next_date_due = next_attempt_date
                CheckoutPaymentAttempt.objects.create(
                    user_subscription=user_sub,
                    ch_user_subscription=ch_user_sub,
                    date_due=next_date_due,
                    retry=attempt.retry + 1
                )
                if user_sub.status != SubStatusChoices.OVERDUE:
                    user_sub_error_fallback(user_sub, SubStatusChoices.OVERDUE)
                    user_subs_count += 1
                    EVENT_MANAGER.sendEvent("pr_funnel_subscription_past_due", user.pk, {'retry': attempt.retry}, topic="funnel")
        elif response.status == 'Authorized':
            # Successful payment
            if settings.DEBUG:
                next_date_due = timezone.now() + timezone.timedelta(minutes=5)
            else:
                next_date_due = timezone.now() + billing_cycle_to_relativedelta(sub.billing_cycle_frequency, sub.billing_cycle_interval)
            next_attempt_date = next_date_due  # used to send correct date with the "pr_funnel_recurring_payment" event
            expires = next_date_due + EXPIRES_MARGIN
            user_sub.status = SubStatusChoices.ACTIVE
            user_sub.expires = expires
            user_sub.paid_counter = counter + 1
            user_sub.save()
            user_subs_count += 1
            if counter == 1:
                # subscription.status: trialing -> active
                flag_t_to_s = True
            elif counter > 1:
                # subscription.status: paused -> active or active -> active ( or overdue -> active )
                flag_renewal = True
            CheckoutPaymentAttempt.objects.create(
                user_subscription=user_sub,
                ch_user_subscription=ch_user_sub,
                date_due=next_date_due,
                retry=0
            )
        else:
            logger.error("Checkout: Recurring: Charge attempt returned status '%s' for attempt=%s", response.status, attempt)

        # send payment to pubsub
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
            "order_description": "jobescape_subscription",
            "customer_account_id": user.pk,
            "geo_country": user.funnel_info.get("geolocation", {}).get("country_code", None) if user.funnel_info else None,
            "created_at": created_at,
            "payment_type": "recurring",
            "settle_datetime": created_at,
            "payment_method": getattr(response.source, "card_wallet_type", "card"),
            "subscription_id": sub.pk,
            "started_at": started_at,
            "subscription_status": user_sub.status,
            "card_country": response.source.issuer_country,
            "card_brand": response.source.scheme,
            "gross_amount": deconvert_amount(response.amount, response.currency),
            "week_day": requested_on.strftime("%A"),
            "months": months,
            "week_date": week_date,
            "date": requested_on.date(),
            "subscription_cohort_date": requested_on.date(),
            "mid": "checkout",
            "channel": "checkout",
            "paid_count": counter,
            "retry_count": attempt.retry,
            "decline_message": decline_message,
            "is_3ds": three_ds,
            "bin": response.source.bin,
        })

        EVENT_MANAGER.sendEvent("pr_funnel_recurring_payment", user.pk, {
            'subscription': sub.name,
            'retry_number': attempt.retry,
            'response_code': attempt.response_code,
            'response_message': attempt.response_summary,
            'next_payment_date': next_attempt_date
        }, topic="funnel")
        if flag_renewal:
            EVENT_MANAGER.sendEvent('pr_funnel_subscription_renewal', user.pk, {"count": user_sub.paid_counter}, topic="funnel")
        if flag_t_to_s:
            EVENT_MANAGER.sendEvent("pr_funnel_trial_to_subscription", user.pk, topic="funnel")

    return {
        "updated_attempts": updated_attempts_count,
        "updated_usubscriptions": user_subs_count,
    }


# @app.task(ignore_result=True)  # TODO (DEV-119): Merge with the above
def run_charge_users_new():
    # Fetch all due payment attempts
    queryset = CheckoutPaymentAttempt.objects.filter(executed=False, date_due__lt=timezone.now())\
        .select_related("ch_user_subscription__user_subscription__user__checkout_customer")\
        .prefetch_related("ch_user_subscription__user_subscription__subscription")
    api = CheckoutAPI()
    new_attempts_count = 0
    updated_attempts_count = 0
    user_subs_count = 0
    ch_trans_count = 0
    for attempt in queryset:
        # ch_user_sub = attempt.ch_user_subscription
        user_sub = attempt.user_subscription
        # payment_id = ch_user_sub.payment_id
        # source_id = ch_user_sub.source_id
        # user_sub = ch_user_sub.user_subscription
        if user_sub.status not in [SubStatusChoices.ACTIVE, SubStatusChoices.TRIALING, SubStatusChoices.OVERDUE]:
            logger.debug("Checkout: Recurring: Skipping because UserSubscription has inappropriate status=%s", user_sub.status)
            attempt_error_fallback(attempt, "Inappropriate UserSubscription status")
            updated_attempts_count += 1
            continue
        sub = user_sub.subscription
        if not sub:
            logger.warning("Checkout: Recurring: Skipping because UserSubscription is not bound to any Subscription for attempt=%s", attempt)
            attempt_error_fallback(attempt, "No Subscription on UserSubscription")
            updated_attempts_count += 1
            continue
        user = user_sub.user
        if not user:
            logger.warning("Checkout: Recurring: Skipping because UserSubscription is not bound to any CustomUser for attempt=%s", attempt)
            attempt_error_fallback(attempt, "No CustomUser on UserSubscription")
            updated_attempts_count += 1
            continue
        if not user.password:
            logging.warning("Checkout: Recurring: Subscription was cancelled because CustomUser has no password for attempt=%s", attempt)
            user_sub_error_fallback(user_sub, SubStatusChoices.CANCELED)
            user_subs_count += 1
            attempt_error_fallback(attempt, "Empty password on CustomUser")
            updated_attempts_count += 1
            continue
        try:
            pay_method: CheckoutPaymentMethod = user.ch_payment_methods.get(is_selected=True)  # type: ignore
        except Exception as e:
            logging.warning("Checkout: Recurring: Skipping because failed to fetch CheckoutPaymentMethod for attempt=%s due to exception=%s", attempt, str(e))
            attempt_error_fallback(attempt, "Failed to fetch CheckoutPaymentMethod")
            updated_attempts_count += 1
            continue
        source_id = pay_method.source_id
        payment_id = pay_method.payment_id
        if not source_id:
            logger.warning("Checkout: Recurring: Skipping because UserSubscription is not bound to any source_id for attempt=%s", attempt)
            continue
        scheme = pay_method.card_scheme
        if not scheme:
            logger.warning("Checkout: Recurring: Updating card scheme for CheckoutUserSubscription for attempt=%s", attempt)
            try:
                response = api.get_payment_details(payment_id)
                scheme = response.source.scheme
                pay_method.card_scheme = scheme
                pay_method.save()
            except Exception as e:
                logger.warning(
                    "Checkout: Recurring: Failed to update card scheme for CheckoutUserSubscription for attempt=%s due to exception=%s", attempt, str(e))
        try:
            ch_customer: CheckoutCustomer = user.checkout_customer  # type: ignore
        except CheckoutCustomer.DoesNotExist:
            try:
                response = api.create_customer(user.email, user.full_name)
                ch_customer = CheckoutCustomer.objects.create(id=response.id, user=user)
                api.update_instrument(source_id, ch_customer.id)
            except Exception as e:
                logging.warning(
                    "Checkout: Recurring: Skipping because was unable to create customer or update instrument for attempt=%s due to exception=%s", attempt, str(e))
                continue
        customer_id = ch_customer.id
        three_ds = pay_method.three_ds and scheme == "Mastercard"
        amount = sub.price_amount
        currency: Currency = sub.price_currency  # type: ignore
        next_attempt_date, amount = billing_retry_calculation(attempt.retry, amount)
        EVENT_MANAGER = EventManager(user.payment_system)  # type: ignore
        # Event flags to send at the end
        flag_t_to_s = False
        flag_renewal = False

        try:
            response = api.charge(
                amount, payment_id, source_id, customer_id,
                three_ds, currency, ch_customer.ip, user.pk
            )
        except Exception as exc:
            logger.exception("Checkout: Recurring: Skipping attempt_id=%d due to exception=%s", attempt.pk, str(exc))
            continue
        # Immediately save executed attempt
        attempt.response = response.status
        attempt.response_code = response.response_code
        attempt.response_summary = getattr(response, "response_summary", "")
        attempt.executed = True
        attempt.save()
        updated_attempts_count += 1
        # Handle responses
        if response.status == 'Declined':
            logger.warning("Checkout: Recurring: Charge was declined for attempt=%s", attempt)
            if response.response_code in HARD_DECLINE_CODES:
                logger.info("Checkout: Recurring: Subscription retries were cancelled due to response code=%s", response.response_code)
                user_sub_error_fallback(user_sub, SubStatusChoices.CANCELED)
                user_subs_count += 1
            elif attempt.retry >= 4:
                logger.info("Checkout: Recurring: Subscription was cancelled after 4th retry for user_sub=%s", user_sub)
                user_sub_error_fallback(user_sub, SubStatusChoices.CANCELED)
                user_subs_count += 1
            else:
                if settings.DEBUG:
                    next_date_due = timezone.now() + timezone.timedelta(minutes=5)
                else:
                    next_date_due = next_attempt_date
                CheckoutPaymentAttempt.objects.create(
                    user_subscription=user_sub,
                    date_due=next_date_due,
                    retry=attempt.retry + 1
                )
                if user_sub.status != SubStatusChoices.OVERDUE:
                    user_sub_error_fallback(user_sub, SubStatusChoices.OVERDUE)
                    user_subs_count += 1
                    EVENT_MANAGER.sendEvent("pr_funnel_subscription_past_due", user.pk, {'retry': attempt.retry}, topic="funnel")
        elif response.status == 'Authorized':
            # Successful payment
            if settings.DEBUG:
                next_date_due = timezone.now() + timezone.timedelta(minutes=5)
            else:
                next_date_due = timezone.now() + billing_cycle_to_relativedelta(sub.billing_cycle_frequency, sub.billing_cycle_interval)
            next_attempt_date = next_date_due  # used to send correct date with the "pr_funnel_recurring_payment" event
            expires = next_date_due + EXPIRES_MARGIN
            user_sub.status = SubStatusChoices.ACTIVE
            user_sub.expires = expires
            counter = user_sub.paid_counter
            user_sub.paid_counter = counter + 1
            user_sub.save()
            user_subs_count += 1
            if counter == 1:
                # subscription.status: trialing -> active
                flag_t_to_s = True
            elif counter > 1:
                # subscription.status: paused -> active or active -> active ( or overdue -> active )
                flag_renewal = True
            CheckoutPaymentAttempt.objects.create(
                user_subscription=user_sub,
                date_due=next_date_due,
                retry=0
            )
            CheckoutTransaction.objects.create(
                user_subscription=user_sub,
                payment_method=pay_method,
                currency=currency,
                amount=amount,
                payment_id=payment_id,
            )
            ch_trans_count += 1
        else:
            logger.error("Checkout: Recurring: Charge attempt returned status '%s' for attempt=%s", response.status, attempt)

        EVENT_MANAGER.sendEvent("pr_funnel_recurring_payment", user.pk, {
            'subscription': sub.name,
            'retry_number': attempt.retry,
            'response_code': attempt.response_code,
            'response_message': attempt.response_summary,
            'next_payment_date': next_attempt_date
        }, topic="funnel")
        if flag_renewal:
            EVENT_MANAGER.sendEvent('pr_funnel_subscription_renewal', user.pk, {"count": user_sub.paid_counter}, topic="funnel")
        if flag_t_to_s:
            EVENT_MANAGER.sendEvent("pr_funnel_trial_to_subscription", user.pk, topic="funnel")

    return {
        "updated_attempts": updated_attempts_count,
        "new_attempts": new_attempts_count,
        "updated_usubscriptions": user_subs_count,
        "new_transactions": ch_trans_count,
    }
