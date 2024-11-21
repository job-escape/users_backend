import logging

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from pandas import read_csv

from account.models import CustomUser, GatewayChoices
from payment_checkout.api import API
from payment_checkout.models import (CheckoutPaymentMethod,
                                     CheckoutUserSubscription,
                                     ChPaymentMethodTypes)
from subscription.models import (Subscription, SubStatusChoices,
                                 UserSubscription)
from web_analytics.tasks import publishPayment


def migration_script():
    # pay_methods = []
    # users = []
    payment_ids = CheckoutPaymentMethod.objects.all().values_list("payment_id", flat=True)
    qs = CheckoutUserSubscription.objects.exclude(Q(payment_id__in=payment_ids) | Q(source_id__isnull=True) | Q(source_id__exact=""))
    for ch_user_sub in qs.prefetch_related("user_subscription__user").all()[:1000]:
        user_sub = ch_user_sub.user_subscription
        if not user_sub.user:
            continue
        user = user_sub.user
        if user.payment_system == GatewayChoices.APPLE_PAY:
            method = ChPaymentMethodTypes.APPLE_PAY
        elif user.payment_system == GatewayChoices.GOOGLE_PAY:
            method = ChPaymentMethodTypes.GOOGLE_PAY
        elif user.payment_system == GatewayChoices.CHECKOUT:
            method = ChPaymentMethodTypes.CARD
        else:
            continue
        if user.payment_system != GatewayChoices.CHECKOUT:
            user.payment_system = GatewayChoices.CHECKOUT
            user.save()

        ch_user_subs = CheckoutUserSubscription.objects.filter(user_subscription__user=user)
        if not ch_user_subs.exclude(pk=ch_user_sub.pk).exists():
            is_selected = True
        elif CheckoutPaymentMethod.objects.filter(user=user, is_selected=True).exists():
            is_selected = False
        elif user_sub.status in [SubStatusChoices.ACTIVE, SubStatusChoices.TRIALING]:
            is_selected = True
        elif ch_user_subs.exclude(pk=ch_user_sub.pk).filter(user_subscription__status__in=[SubStatusChoices.ACTIVE, SubStatusChoices.TRIALING]).exists():
            is_selected = False
        else:
            is_selected = True

        api = API()
        try:
            response = api.get_payment_details(ch_user_sub.payment_id)
        except:  # pylint: disable=w0702
            logging.warning("Migration: Error requesting payment details! Skipping CheckoutUserSubscription with pk=%d", ch_user_sub.pk)
            continue
        else:
            response = object()
        source = getattr(response, "source", object())
        pay_method = CheckoutPaymentMethod(
            user=user,
            type=method,
            is_selected=is_selected,
            payment_id=ch_user_sub.payment_id,
            source_id=ch_user_sub.source_id or "",
            card_scheme=ch_user_sub.source_scheme or "",
            card_last4=getattr(source, "last4", ""),
            card_exp_month=getattr(source, "expiry_month", ""),
            card_exp_year=getattr(source, "expiry_year", ""),
            fingerprint=getattr(source, "fingerprint", ""),
            three_ds=ch_user_sub.three_ds,
        )
        pay_method.save()
        logging.info("Script: CheckoutUserSubscription.pk = %d", ch_user_sub.pk)
        # pay_methods.append(pay_method)
    # CheckoutPaymentMethod.objects.bulk_create(pay_methods, ignore_conflicts=True)
    # CustomUser.objects.bulk_update(users, fields=['payment_system'])


def get_subscription(amount, currency):
    if currency == 'AUD':
        if amount in [10.59, 7.88]:
            return 12
        if amount in [17.29, 23.24]:
            return 13
        return 14
    if currency == 'SGD':
        if amount in [6.96, 9.36]:
            return 15
        if amount in [20.51, 15.25]:
            return 16
        return 17
    if currency == 'CAD':
        if amount in [9.43, 6.99]:
            return 18
        if amount in [20.66, 15.36]:
            return 19
        return 20
    if currency == "NZD":
        if amount in [11.49, 8.55]:
            return 21
        if amount in [25.22, 18.75]:
            return 22
        return 23
    if currency == "GBP":
        if amount in [5.54, 4.12]:
            return 24
        if amount in [12.15, 8.99]:
            return 25
        return 26
    if currency == "EUR":
        if amount in [6.45, 4.79]:
            return 27
        if amount in [14.13, 10.49]:
            return 28
        return 29
    if currency == "AED":
        if amount in [25.45, 18.98]:
            return 30
        if amount in [55.79, 41.55]:
            return 31
        return 32
    # else:
    if amount in [5.15, 6.93]:
        return 2
    if amount in [15.19, 11.29]:
        return 3
    return 4


def migrate_payments_historical(url: str, url_2: str):
    all_payments = read_csv(url)
    already = read_csv(url_2)
    already = list(already['order_id'].to_numpy())
    all_payments = all_payments.sort_values(by='Action Date UTC', ascending=True).reset_index(drop=True)
    firsts = all_payments.loc[all_payments['Payment Type'] == "Regular"]
    length = len(firsts.index)
    remove_list = []
    counter = 0
    for i, first in firsts.iterrows():
        counter += 1
        print(f"Прогресс: {round(counter*100/length, 3)}%", end="\r")
        next_payments = all_payments.loc[(all_payments["Card Fingerprint"] == first["Card Fingerprint"]) & (
            all_payments.index >= i) & (~all_payments["Payment ID"].isin(remove_list)) & (~all_payments["Payment ID"].isin(already))]
        first_registered = False
        user = None
        subscription = None
        paid_counter = 0
        retry_counter = 0
        user_sub = None
        for i, next_payment in next_payments.iterrows():
            remove_list.append(next_payment['Payment ID'])
            if next_payment["Wallet"] == "APPLEPAY":
                payment_method = "applepay"
            elif next_payment["Wallet"] == "GOOGLEPAY":
                payment_method = "googlepay"
            else:
                payment_method = "card"
            if str(next_payment["Response Code"]) == "10000" and next_payment["Action Type"] == "Authorisation":
                continue
            elif next_payment["Action Type"] == "Authorisation" and next_payment['Payment Type'] == "Regular" and str(next_payment["Response Code"]) != "10000":
                user_decline = None
                if CustomUser.objects.filter(email=next_payment["Customer Email"]).exists():
                    user_decline = CustomUser.objects.get(email=next_payment["Customer Email"])
                publish_payment(
                    response={
                        "requested_on": next_payment['Action Date UTC'],
                        "id": next_payment['Payment ID'],
                        "amount": int(next_payment['Amount']*100),
                        "gross_amount": next_payment['Amount'],
                        "currency": next_payment['Currency Symbol'],
                        'issuer_country': next_payment['Currency Symbol'],
                        'scheme': 'Visa' if next_payment['Payment Method Name'] == "VISA" else "Mastercard",
                        'bin': next_payment['CC BIN']
                    }, user=user_decline,
                    subscription=Subscription.objects.get(pk=get_subscription(
                        amount=next_payment['Amount'], currency=next_payment['Currency Symbol'])),
                    res_status="declined" if str(next_payment["Response Code"]) != "10000" else "settled",
                    user_sub=None,
                    data={
                        "decline_message": str(next_payment["Response Description"]),
                        "is_3ds": next_payment["Is 3DS"],
                        "payment_method": payment_method,
                        "payment_type": "first"
                    }
                )
                continue
            elif str(next_payment["Response Code"]) == "10000" and next_payment["Action Type"] == "Capture" and next_payment['Payment Type'] == "Regular":
                if first_registered:
                    break
                first_registered = True
                if CheckoutUserSubscription.objects.filter(payment_id=next_payment['Payment ID']).exists():
                    user_sub = CheckoutUserSubscription.objects.filter(payment_id=next_payment['Payment ID'])[0].user_subscription
                    subscription = user_sub.subscription
                    user = user_sub.user
            if str(next_payment["Response Code"]) == "10000" and next_payment["Action Type"] == "Capture" and next_payment['Payment Type'] == "Recurring":
                paid_counter += 1
            publish_payment(
                response={
                    "requested_on": next_payment['Action Date UTC'],
                    "id": next_payment['Payment ID'],
                    "amount": int(next_payment['Amount']*100),
                    "gross_amount": next_payment['Amount'],
                    "currency": next_payment['Currency Symbol'],
                    'issuer_country': next_payment['Currency Symbol'],
                    'scheme': 'Visa' if next_payment['Payment Method Name'] == "VISA" else "Mastercard",
                    'bin': next_payment['CC BIN']
                },
                user=user,
                subscription=subscription,
                res_status="declined" if str(next_payment["Response Code"]) != "10000" else "settled",
                user_sub=user_sub,
                data={
                    "decline_message": str(next_payment["Response Description"]),
                    "is_3ds": next_payment["Is 3DS"],
                    "payment_method": payment_method,
                    "payment_type": "first" if next_payment['Payment Type'] == "Regular" else "recurring",
                    "paid_count": paid_counter,
                    "retry_count": retry_counter,
                }
            )
            if str(next_payment["Response Code"]) != "10000" and next_payment['Payment Type'] == "Recurring":
                retry_counter += 1
            if str(next_payment["Response Code"]) == "10000" and next_payment["Action Type"] == "Capture" and next_payment['Payment Type'] == "Recurring":
                retry_counter = 0


def publish_payment(
    response, res_status: str, user: CustomUser | None = None, subscription: Subscription | None = None,
    user_sub: UserSubscription | None = None, data: dict | None = None
):
    requested_on = timezone.datetime.strptime(response['requested_on'], "%Y-%m-%d %H:%M:%S")
    created_at = int(requested_on.timestamp() * 1e6)
    months = int(requested_on.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1e6)
    week_date = (requested_on - timezone.timedelta(days=requested_on.weekday())).date()
    funnel_info = user.funnel_info if user else {}
    d = {
        "order_id": response['id'],
        "status": res_status,
        "amount": response['amount'],
        "currency": response['currency'],
        "order_description": "jobescape_subscription",
        "customer_account_id": user.pk if user else None,
        "geo_country": funnel_info.get("geolocation", {}).get("country_code", None) if funnel_info else None,
        "created_at": created_at,
        "payment_type": "first",
        "settle_datetime": created_at,
        "payment_method": 'card',
        "subscription_id": subscription.pk if subscription else None,
        "started_at": created_at,
        "subscription_status": user_sub.status if user_sub else None,
        "card_country": response['issuer_country'],
        "card_brand": response['scheme'],
        "gross_amount": response['gross_amount'],
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
        "bin": response['bin']
    }
    if data:
        d.update(data)
    return publishPayment(settings.PUBSUB_PM_TOPIC_ID, d)
