from django.utils import timezone
from growthbook import GrowthBook

from account.models import CustomUser
from shared.emailer import assign_to_group, remove_from_addressbook
from subscription.models import Subscription
from web_analytics.event_manager import EventManager
from google_tasks.tasks import create_delay_registration_email_task


def post_purchase(user: CustomUser, subscription: Subscription, gb: GrowthBook, em: EventManager, props: dict):
    """
        This function performs post-purchase operations common to all payment systems.
        Includes queuing registration email, removing from email cascade, sending purchase event.
    """
    # Send delayed email
    # delay_registration_email.apply_async(args=[user.pk, 1], eta=timezone.now() + timezone.timedelta(minutes=5))
    create_delay_registration_email_task(user_id=user.pk, cascade=1, delay_minutes=5)
    # Remove from "confirm email" cascade
    remove_from_addressbook(user.email)
    # Handle particular case and put users to a mail group
    if subscription.pk in [3, 4] and user.country_code in ['US', 'CA', 'GB', 'SG', 'AU', 'NZ']:
        assign_to_group(user.email, 130813110010250444, data={"name": user.full_name})
    # Identify user in growthbook
    gb.set_attributes({"id": str(user.pk)})

    props.update({
        "subscription_id": subscription.pk,
        "currency": subscription.price_currency,
    })
    fb_event_id = em.sendPurchaseEvent(
        user.pk,
        user.device_id,
        user.email,
        subscription.name,
        user.funnel_info,
        props,
    )
    return fb_event_id
