from django.contrib import admin

from payment_checkout.fraud_models import FraudPayment
from payment_checkout.models import (CheckoutCustomer, CheckoutPaymentAttempt,
                                     CheckoutPaymentMethod,
                                     CheckoutTransaction,
                                     CheckoutUserSubscription)


@admin.register(CheckoutUserSubscription)
class CheckoutUserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user_subscription', 'payment_id', 'source_id')
    search_fields = ['user_subscription__user__email', 'payment_id', 'source_id']
    readonly_fields = ('user_subscription', 'payment_id')
    list_select_related = ('user_subscription__user', 'user_subscription__subscription')


@admin.register(CheckoutCustomer)
class CheckoutCustomerAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user')
    search_fields = ('user__email', 'pk')
    readonly_fields = ('user',)
    list_select_related = ('user',)


@admin.register(CheckoutPaymentAttempt)
class CheckoutPaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('pk', 'date_due', 'executed', 'response', 'response_code', 'response_summary', 'retry', 'ch_user_subscription')
    search_fields = ('date_due', 'executed', 'response', 'response_code', 'response_summary', 'retry')
    readonly_fields = ('ch_user_subscription', 'user_subscription')


@admin.register(FraudPayment)
class FraudPaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('email', 'ip', 'datetime', 'fingerprint')
    search_fields = ['email', 'fingerprint', 'ip']


@admin.register(CheckoutPaymentMethod)
class CheckoutPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user', 'type', 'is_selected')
    search_fields = ('pk', 'user', 'type', 'is_selected')
    readonly_fields = ('user',)


@admin.register(CheckoutTransaction)
class CheckoutTransactionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user_subscription', 'payment_method')
    search_fields = ('pk', 'user_subscription',)
    readonly_fields = ('user_subscription',)
