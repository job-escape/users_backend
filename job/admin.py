from django.contrib import admin
from job.models import Job, Company
# Register your models here.

class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'expired', 'date_modified')
    search_fields = ['title', 'expired']

admin.site.register(Company)
admin.site.register(Job, JobAdmin)