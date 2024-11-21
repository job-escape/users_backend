# accounts/models.py

import secrets

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from custom.custom_validators import validate_lowercase


class GatewayChoices(models.TextChoices):  # TODO (DEV-122)
    # PADDLE = 'paddle', _('Paddle')  # TODO: remove
    # PAYTABS = 'paytabs', _('Paytabs')  # TODO: remove
    # PAYPAL = 'paypal', _('PayPal')  # TODO: move to PaymentMethods?
    SOLIDGATE = 'solidgate', _('Solidgate')
    # ROCKETGATE = 'rocketgate', _('Rocketgate')
    # STRIPE = 'stripe', _('Stripe')  # TODO: remove
    CHECKOUT = 'checkout', _('Checkout')
    # APPLE_PAY = 'apple_pay', _('Apple Pay')  # TODO: remove
    # CHECKOUT_PAYPAL = 'checkout_paypal', _('Checkout PayPal')  # TODO: remove
    # GOOGLE_PAY = 'google_pay', _('Google Pay')  # TODO: remove


def get_default_video_due():
    return timezone.now() + timezone.timedelta(days=30)


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        email = email.lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(_("Email address"), unique=True, validators=[validate_lowercase])
    full_name = models.CharField(_("Full name"), max_length=150, blank=True)
    payment_email = models.EmailField(_("Payment email"), null=True, blank=True)
    payment_system = models.CharField(_("Payment system"), choices=GatewayChoices.choices, default=GatewayChoices.CHECKOUT)
    image = models.CharField(_("Profile Image"), null=True, blank=True, max_length=200)

    email_consent = models.BooleanField(_("Consent for receiving emails"), null=True, blank=True)
    job_notification = models.BooleanField(default=False, help_text="Designates if the user agreed to receive job notifications")
    trustpilot_review = models.BooleanField(default=False, help_text="Whether the user left a TrustPilot review or not")

    token = models.CharField(_("Registration Token"), null=True, blank=True)
    token_set_time = models.DateTimeField(_("The time last token was set"), null=True, blank=True)
    code = models.CharField(_("Password Set/Update Code"), null=True, blank=True)
    code_set_time = models.DateTimeField(_("The time last code was set"), null=True, blank=True)

    # personal_plan = models.ForeignKey("personal_plan.PersonalPlan", verbose_name="Personal Plan", null=True, blank=True, on_delete=models.SET_NULL)
    personal_plan_pk = models.CharField(verbose_name="Personal Plan", null=True, blank=True)
    prompt_upsell = models.BooleanField(default=False, help_text="Prompt Upsell paid")
    mentor_upsell = models.BooleanField(default=False, help_text="Mentor Upsell paid")
    funnel_info = models.JSONField(_("Funnel information"), null=True, blank=True)
    country_code = models.CharField(_("Country code"), null=True, blank=True)
    device_id = models.CharField(_("Last device ID"), default="Unknown")

    video_credit = models.PositiveIntegerField(_("Remaining video credits"), default=10)
    video_credit_due = models.DateTimeField(_("Video credit reset time"), default=get_default_video_due)

    d2_csat = models.BooleanField(default=False, help_text="Show D2 CSAT?")
    d3_csat = models.BooleanField(default=False, help_text="Show D3 CSAT?")
    ai_csat = models.BooleanField(default=False, help_text="Show AI CSAT?")

    ab_test_48 = models.CharField(default=None, verbose_name="AB test 48", null=True, blank=True)
    ab_test_51 = models.CharField(default=None, verbose_name="AB test 51", null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    # paddle_customer = one-to-one with PaddleCustomer
    # paytabs_customer = one-to-one with PaytabsCustomer
    # paypal_customer = one-to-one with PayPalCustomer
    # checkout_customer = one-to-one with CheckoutCustomer
    # ch_payment_methods = one-to-many with CheckoutPaymentMethod
    # subscriptions = one-to-many with UserSubscription
    # unit_feedbacks = one-to-many with UnitFeedback
    # card_feedbacks = one-to-many with CardFeedback
    # subscription_feedbacks = one-to-many with SubscriptionFeedback
    # paytabs_bill_attempt = one-to-many with PaytabsBillAttempt
    # projects = one-to many with Project

    # first_name = CharField
    # last_name = CharField
    # is_active = BooleanField

    objects = UserManager()  # type: ignore

    def set_register_token(self):
        '''Creates and sets `token` on instance, and saves the instance. Returns the token.'''
        token = secrets.token_urlsafe()
        self.token = token
        self.token_set_time = timezone.now()
        self.save()
        return token

    def __str__(self):
        return f"User[{self.pk}] {self.email}"


class UserOnboarding(models.Model):
    user = models.OneToOneField(CustomUser, models.CASCADE, primary_key=True, related_name="onboarding", verbose_name=_("User"))
    registration = models.BooleanField(_("Completed registration?"), default=False)
    first_course = models.BooleanField(_("First course?"), default=False)
    first_project = models.BooleanField(_("First project?"), default=False)
    first_interview = models.BooleanField(_("First interview?"), default=False)
    lab = models.BooleanField(_("Lab onboarding?"), default=False)
    first_text = models.BooleanField(_("First text generation?"), default=False)
    first_image = models.BooleanField(_("First image generation?"), default=False)
    first_video = models.BooleanField(_("First video generation?"), default=False)
