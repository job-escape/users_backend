from django.db import models
from django.utils.translation import gettext_lazy as _

from account.models import CustomUser
from subscription.models import Currency, UserSubscription

from .fraud_models import FraudPayment


class ChPaymentMethodTypes(models.TextChoices):
    APPLE_PAY = 'apple_pay', _('Apple Pay')
    GOOGLE_PAY = 'google_pay', _('Google Pay')
    CARD = 'card', _('Card')


class CheckoutCustomer(models.Model):
    id = models.CharField(verbose_name=_("ID"), max_length=30, primary_key=True)
    user = models.OneToOneField(CustomUser, verbose_name=_("User"), on_delete=models.CASCADE, related_name="checkout_customer")
    ip = models.CharField(_("IP address"), max_length=50, blank=True)


class CheckoutUserSubscription(models.Model):  # TODO (DEV-119): remove this model
    user_subscription = models.OneToOneField(UserSubscription, models.CASCADE, verbose_name=_(
        "User Subscription"), related_name="checkout_user_subscription")
    payment_id = models.CharField(_("User Payment ID"))
    source_id = models.CharField(_("Source ID"), null=True, blank=True)
    source_scheme = models.CharField(_("Card scheme"), null=True, blank=True)
    three_ds = models.BooleanField(_("Has 3DS/3RI?"), default=False, blank=True)
    # attempts

    class Meta:
        indexes = [
            models.Index(fields=["user_subscription"]),
            models.Index(fields=["payment_id"])
        ]

    def __str__(self):
        return f"CheckoutUserSubscription[{self.pk}]"


class CheckoutPaymentAttempt(models.Model):
    ch_user_subscription = models.ForeignKey(CheckoutUserSubscription, models.CASCADE, related_name="attempts",
                                             verbose_name=_("Checkout user subscription"), null=True)  # TODO (DEV-119): remove this field
    user_subscription = models.ForeignKey(UserSubscription, models.CASCADE, verbose_name=_("User subscription"))
    date_due = models.DateTimeField(_("Datetime of the attempt"))
    retry = models.PositiveSmallIntegerField(_("Retry counter"), default=0)
    executed = models.BooleanField(_("Is attempt executed?"), default=False, blank=True)
    response = models.CharField(_("Checkout response status"), default="", blank=True)
    response_code = models.CharField(_("Checkout response code"), default="", blank=True)
    response_summary = models.CharField(_("Checkout response summmary"), default="", blank=True)
    date_created = models.DateTimeField(_("Datetime created"), auto_now_add=True)
    date_updated = models.DateTimeField(_("Datetime updated"), auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["-date_due", "executed"], condition=models.Q(executed=False),
                         name="checkout-payment--index")
        ]

    def __str__(self):
        return f"CheckoutPaymentAttempt[{self.pk}]"


class CheckoutPaymentMethod(models.Model):
    user = models.ForeignKey(CustomUser, models.CASCADE, verbose_name=_("User"), related_name="ch_payment_methods")
    type = models.CharField(_("Type"), max_length=15, choices=ChPaymentMethodTypes.choices)
    is_selected = models.BooleanField(_("Is selected?"))
    payment_id = models.CharField(_("Payment ID"), max_length=30)
    source_id = models.CharField(_("Source ID"), max_length=30, blank=True)
    card_scheme = models.CharField(_("Card scheme"), max_length=15, blank=True)
    card_last4 = models.CharField(_("Card last 4"), max_length=5, blank=True)
    card_exp_month = models.CharField(_("Card expiration month"), max_length=9, blank=True)
    card_exp_year = models.CharField(_("Card expiration year"), max_length=5, blank=True)
    fingerprint = models.CharField(_("Fingerprint"), max_length=100, blank=True)
    three_ds = models.BooleanField(_("Uses 3DS/3RI?"), default=False, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_selected'], name="method--user-is_selected-unique-constraint", condition=models.Q(is_selected=True)
            ),
        ]
        indexes = [
            models.Index(fields=["payment_id", "user"])
        ]


class CheckoutTransaction(models.Model):
    user_subscription = models.ForeignKey(UserSubscription, verbose_name=_("User subscription"), on_delete=models.CASCADE)
    payment_method = models.ForeignKey(CheckoutPaymentMethod, verbose_name=_("Checkout payment method"), on_delete=models.CASCADE)
    currency = models.CharField(_("Currency"), max_length=5, choices=Currency.choices, default=Currency.USD)
    amount = models.FloatField(_("Amount"), default=0)
    payment_id = models.CharField(_("Transaction payment ID"), max_length=30)
    date_created = models.DateTimeField(_("Datetime created"), auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["payment_id"])
        ]


class Checkout3dsPayment(models.Model):
    id = models.CharField(_("ID"), max_length=30, primary_key=True)
    user_subscription = models.ForeignKey(UserSubscription, models.CASCADE, verbose_name=_(
        "User subscription"))
