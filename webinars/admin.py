from django.contrib import admin

from webinars.models import Webinar


@admin.register(Webinar)
class WebinarAdmin(admin.ModelAdmin):
    list_display = ('title',)
