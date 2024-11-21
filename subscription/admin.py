from django.contrib import admin
from import_export.admin import ExportActionModelAdmin

from web_analytics.event_manager import EventManager
from .models import (Subscription, SubscriptionFeedback, Transaction,
                     UserSubscription, Upsell, UserUpsell, SubStatusChoices)

# Register your models here.


class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_currency', 'trial_period_interval', 'trial_cycle_frequency', 'trial_standard_price_amount',
                    'billing_cycle_interval', 'billing_cycle_frequency', 'price_amount',)
    search_fields = ['name', 'trial_period_interval', 'trial_cycle_frequency',
                     'trial_standard_price_amount', 'billing_cycle_interval', 'billing_cycle_frequency', 'price_amount']


class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription', 'date_started', 'status', 'paid_counter',)
    search_fields = ['user__email', 'subscription__name', 'date_started', 'status', 'paid_counter', 'user__id']
    readonly_fields = ('user',)
    list_select_related = ('user', 'subscription')
    
    def save_model(self, request, obj, form, change):
        if change:  # Check if the object is being updated
            old_instance = UserSubscription.objects.get(pk=obj.pk)
            if old_instance.status in [SubStatusChoices.ACTIVE, SubStatusChoices.OVERDUE, SubStatusChoices.TRIALING]:
                if obj.status == SubStatusChoices.CANCELED:
                    EventManager(obj.user.payment_system).sendEvent(  # type: ignore
                        "pr_webapp_unsubscribed", obj.user.pk, {"unsubscribe_reason": "support request"}, topic="app"
                    )
        super().save_model(request, obj, form, change)


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_id', 'date_created', 'payment_system',)
    search_fields = ['user__email', 'transaction_id', 'date_created', 'payment_system',]
    list_select_related = ('user',)


class SubscriptionFeedbackAdmin(ExportActionModelAdmin, admin.ModelAdmin):
    list_display = ('user', 'comment', 'date_created', )
    search_fields = ['user__email', 'comment', 'date_created',]
    readonly_fields = ('user',)
    list_select_related = ('user',)



class UpsellAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_amount', 'price_chase_amount', 'price_currency',)
    search_fields = ['name', 'price_amount', 'price_chase_amount', 'price_currency']


class UserUpsellAdmin(admin.ModelAdmin):
    list_display = ('user', 'upsell', 'paid',)
    search_fields = ['user__email', 'upsell__name', 'paid']
    readonly_fields = ('user',)
    list_select_related = ('user', 'upsell')

# admin.site.register(Gateway)
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(UserSubscription, UserSubscriptionAdmin)
admin.site.register(SubscriptionFeedback, SubscriptionFeedbackAdmin)

admin.site.register(Upsell, UpsellAdmin)
admin.site.register(UserUpsell, UserUpsellAdmin)
