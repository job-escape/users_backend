from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from account.models import CustomUser, GatewayChoices


class SubTypeChoices(models.IntegerChoices):
    BASIC = 0, _('Basic')
    FULL = 1, _('Full')
    EXTRA = 2, _('Extra')


class SubscriptionTypes(models.TextChoices):
    BASIC = 'basic', _('Basic')
    FULL = 'full', _('Full')
    EXTRA = 'extra', _('Extra')


class SubStatusChoices(models.TextChoices):
    ACTIVE = 'active', _('Active')
    OVERDUE = 'past_due', _('Overdue')  # Solidgate uses 'Redemption'
    PAUSED = 'paused', _('Paused')
    TRIALING = 'trialing', _('Trialing')
    CANCELED = 'canceled', _('Canceled')
    INACTIVE = 'inactive', _('Inactive')


class TrialPriceChoices(models.TextChoices):
    STANDARD = 'standard', _('Standard')
    CHASE = 'chase', _('Chase')
    TIMEOUT = 'timeout', _('Timeout')


class BillingCycleIntervals(models.TextChoices):
    DAY = 'day', _('Day')
    WEEK = 'week', _('Week')
    MONTH = 'month', _('Month')
    YEAR = 'year', _('Year')


class Currency(models.TextChoices):
    # Be sure to check how values are converted and deconverted for payment_checkout
    AED = 'AED'
    USD = 'USD'
    AUD = 'AUD'
    SGD = 'SGD'
    CAD = 'CAD'
    NZD = 'NZD'
    GBP = 'GBP'
    EUR = 'EUR'


class SubscriptionType:
    subscription_type = None


class BasicSubscription(SubscriptionType):
    subscription_type = SubTypeChoices.BASIC


class FullSubscription(SubscriptionType):
    subscription_type = SubTypeChoices.FULL


class ExtraSubscription(SubscriptionType):
    subscription_type = SubTypeChoices.EXTRA


class Subscription(models.Model):
    name = models.CharField(verbose_name="Name (title)", max_length=100, default="", blank=True)
    price_amount = models.FloatField(verbose_name="Subscription price", default=1, blank=True)
    price_currency = models.CharField(verbose_name="Subscription price currency code", max_length=5,
                                      blank=False, default=Currency.USD, choices=Currency.choices)
    price_currency_symbol = models.CharField(verbose_name="Price currency symbol", max_length=10,
                                             blank=True, default="$", help_text="For example: $")
    subscription_type = models.CharField(verbose_name="Subscription type", choices=SubscriptionTypes.choices,
                                         default=SubscriptionTypes.BASIC, blank=True)
    is_default = models.BooleanField(verbose_name="Is default on the selling page?", default=False)

    billing_cycle_interval = models.CharField(verbose_name="Billing cycle interval", max_length=5,
                                              choices=BillingCycleIntervals.choices, default=BillingCycleIntervals.DAY, blank=True)
    billing_cycle_frequency = models.PositiveIntegerField(verbose_name="Billing cycle frequency", default=1, blank=True)
    trial_timeout_price_amount = models.FloatField(verbose_name="Trial timeout price", default=1, blank=True)
    trial_standard_price_amount = models.FloatField(verbose_name="Trial stardard price", default=1, blank=True)
    trial_standard_discount = models.PositiveIntegerField(verbose_name="Trial stardard discount", default=90, blank=True, help_text="90 by default")
    trial_price_chase_amount = models.FloatField(verbose_name="Trial chase price", default=1, blank=True)
    trial_chase_discount = models.PositiveIntegerField(verbose_name="Trial chase discount", default=95, blank=True, help_text="95 by default")
    trial_price_currency = models.CharField(verbose_name="Trial price currency code", max_length=5,
                                            blank=True, default="USD", help_text="For example: USD")
    trial_period_interval = models.CharField(verbose_name="Trial period interval", max_length=5,
                                             choices=BillingCycleIntervals.choices, default=BillingCycleIntervals.DAY, blank=True)
    trial_cycle_frequency = models.PositiveIntegerField(verbose_name="Trial cycle frequency", default=1, blank=True)

    # paddle_price = one-to-one with PaddlePrice
    # paddle_subscription = one-to-one with PaddleSubscription
    # paypal_subscription = one-to-one with PayPalSubscription
    # solidgate_subscription = one-to-one with SolidgateSubscription
    # rocketgate_subscription = one-to-one with RocketgateSubscription
    # stripe_subscription = one-to-one with StripeSubscription

    def __str__(self):
        return f"Subscription[{self.pk}] {self.name}"


class UserSubscription(models.Model):
    user = models.ForeignKey(CustomUser, verbose_name="User", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="subscriptions")
    subscription = models.ForeignKey(Subscription, verbose_name="Subscription",
                                     null=True, blank=True, on_delete=models.SET_NULL)
    date_started = models.DateField(verbose_name="Activation date", default=now, blank=True)
    expires = models.DateTimeField(default=now, verbose_name="Expiration Date", blank=True)
    status = models.CharField(choices=SubStatusChoices.choices, default=SubStatusChoices.ACTIVE, verbose_name="Subscription status")
    paid_counter = models.PositiveBigIntegerField(verbose_name="Number of times the subscription was paid (renewed+1)", default=0, blank=True)
    notification_sent = models.BooleanField(verbose_name="Was pre-billing notification sent?", null=True, blank=True)
    # paddle_user_subscription = one-to-one with PaddleUserSubscription
    # paytabs_user_subscription = one-to-one with PaytabsUserSubscription
    # paypal_user_subscription = one-to-one with PayPalUserSubscription
    # solidgate_user_subscription = one-to-one with SolidgateUserSubscription
    # rocketgate_user_subscription = one-to-one with RocketgateUserSubscription -- NOT IMPLEMENTED
    # stripe_user_subscription = one-to-one with StripeUserSubscription
    # checkout_user_subscription = one-to-one with CheckoutUserSubscription

    def __str__(self):
        return f"UserSubscription[{self.pk}]"


class Transaction(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="User", related_name="transactions", null=True, blank=True)
    date_created = models.DateTimeField(verbose_name="Date Created", auto_now_add=True)
    transaction_id = models.CharField(verbose_name="Transaction ID", max_length=50)
    payment_system = models.CharField(choices=GatewayChoices.choices, verbose_name="Payment system", null=True)

    def __str__(self):
        return f"Transaction[{self.pk}] {self.date_created}"


class SubscriptionFeedback(models.Model):
    comment = models.TextField(verbose_name="Comment", default="", blank=True)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL,
                             verbose_name="User (Author)", related_name="subscription_feedbacks", null=True, blank=True)
    date_created = models.DateTimeField(verbose_name="Date Created", auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"SubscriptionFeedback[{self.pk}] {self.date_created}"

class Upsell(models.Model):
    name = models.CharField(verbose_name="Name (title)", max_length=100, default="", blank=True)
    template_id = models.IntegerField(verbose_name="Email template", default=37599414)
    email_bool = models.BooleanField(verbose_name="Email on upsell?", default=True)
    price_amount = models.FloatField(verbose_name="Upsell price", default=1, blank=True)
    price_chase_amount = models.FloatField(verbose_name="Upsell chase price", default=1, blank=True)
    price_currency = models.CharField(verbose_name="Subscription price currency code", max_length=5,
                                      blank=False, default=Currency.USD, choices=Currency.choices)
    price_currency_symbol = models.CharField(verbose_name="Price currency symbol", max_length=10,
                                             blank=True, default="$", help_text="For example: $")
    def __str__(self):
        return f"Upsell[{self.pk}] {self.name}"

class UserUpsell(models.Model):
    user = models.ForeignKey(CustomUser, verbose_name="User", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="upsells")
    upsell = models.ForeignKey(Upsell, verbose_name="Upsell",
                                     null=True, blank=True, on_delete=models.SET_NULL)
    paid = models.BooleanField(verbose_name="Paid ?", default=False)
    
    def __str__(self):
        return f"UserUpsell[{self.pk}]"