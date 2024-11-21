from django.db import models
from django.utils.translation import gettext_lazy as _
from subscription.models import Subscription, UserSubscription


class SolidgateSubscription(models.Model):
    trial_timeout_subscription_id = models.CharField(verbose_name="Timeout Trial subscription (product) ID", max_length=50)
    trial_standard_subscription_id = models.CharField(verbose_name="Standard Trial subscription (product) ID", max_length=50)
    trial_chase_subscription_id = models.CharField(verbose_name="Chase Trial subscription (product) ID", max_length=50)
    subscription = models.OneToOneField(Subscription, verbose_name="Our Subscription", on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name="solidgate_subscription")
    def __str__(self):
        return f"SolidgateSubscription[{self.pk}]"


class SolidgateUserSubscription(models.Model):
    subscription_id = models.CharField(verbose_name="Solidgate user subscription ID", max_length=100)
    user_subscription = models.OneToOneField(UserSubscription, verbose_name="User Subscription",
                                             on_delete=models.CASCADE, related_name="solidgate_user_subscription")
    card_token = models.CharField(verbose_name="Card Token for one-click payments", max_length=100, default="")    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['subscription_id'], name="solidgate-user-subscription--unique-constraint")
        ]

    def __str__(self):
        return f"SolidgateUserSubscription[{self.pk}]"

class PaypalDispute(models.Model):
    dispute_id = models.CharField(_("Dispute ID"), max_length=50, default="", blank=True)
    refunded = models.BooleanField(_("Refunded?"), default=False)
    amount = models.IntegerField(_("Amount"), default=0)
    order_id = models.CharField(_("Order ID"), default="", blank=True)
    def __str__(self):
        return f"{self.dispute_id}"