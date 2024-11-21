from django.contrib import admin

from payment_solidgate.models import (SolidgateSubscription,
                                      SolidgateUserSubscription,
                                      PaypalDispute)

# Register your models here.


class SolidgateSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('subscription',  'trial_standard_subscription_id', 'trial_chase_subscription_id', 'trial_timeout_subscription_id')
    search_fields = ['subscription__name', 'trial_standard_subscription_id', 'trial_chase_subscription_id', 'trial_timeout_subscription_id']


# class SolidgateCustomerAdmin(admin.ModelAdmin):
#     list_display = ('user', 'id',)
#     search_fields = ['user__email', 'id']


class SolidgateUserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user_subscription', 'subscription_id',)
    search_fields = ['user_subscription__user__email', 'subscription_id']
    readonly_fields = ('user_subscription',)


admin.site.register(SolidgateSubscription, SolidgateSubscriptionAdmin)
# admin.site.register(SolidgateCustomer, SolidgateCustomerAdmin)
admin.site.register(SolidgateUserSubscription, SolidgateUserSubscriptionAdmin)
# admin.site.register(PaypalDispute)
