from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _
from import_export.admin import ExportActionMixin
from nested_admin import nested

from account.models import CustomUser, UserOnboarding
from payment_checkout.models import CheckoutUserSubscription
from subscription.models import SubscriptionFeedback, UserSubscription


class CheckoutUserSubscriptionInline(nested.NestedStackedInline):
    model = CheckoutUserSubscription
    extra = 0


class SubscriptionFeedbackInline(nested.NestedStackedInline):
    model = SubscriptionFeedback
    extra = 0


class UserSubscriptionInline(nested.NestedStackedInline):
    model = UserSubscription
    inlines = (CheckoutUserSubscriptionInline,)
    extra = 0


class UserOnboardingInline(nested.NestedStackedInline):
    model = UserOnboarding


@admin.register(CustomUser)
class UserAdmin(ExportActionMixin, DjangoUserAdmin, nested.NestedModelAdmin):
    """Define admin model for custom User model with no email field."""
    list_per_page = 20
    fieldsets = (
        (None, {'fields': ('email', 'password', 'full_name', 'first_name', 'last_name')}),
        (_('Personal info'), {'fields': ('payment_email', 'payment_system', 'funnel_info', 'country_code', 'image', )}),
        (_('Preferences'), {'fields': ('email_consent', 'job_notification', 'trustpilot_review', 'personal_plan_pk', 'prompt_upsell',
                                        'mentor_upsell', 'd2_csat', 'd3_csat', 'ai_csat', 'ab_test_48', 'ab_test_51')}),
        (_('Token info'), {'fields': ('token', 'token_set_time', 'code', 'code_set_time')}),
        (_('Permissions'), {'fields': ('is_active',  'is_superuser',)}),
        (_('Video credits'), {'fields': ('video_credit',  'video_credit_due',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'full_name', 'date_joined')
    search_fields = ('email', 'full_name', 'id')
    ordering = ()
    inlines = (UserSubscriptionInline, SubscriptionFeedbackInline, UserOnboardingInline,)
    show_full_result_count = False
