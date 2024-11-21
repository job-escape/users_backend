from django.db import models
from django.utils.translation import gettext_lazy as _


class GatewayChoices(models.TextChoices):
    SOLIDGATE = 'solidgate', _('Solidgate')
    CHECKOUT = 'checkout', _('Checkout')