from django.contrib import admin

from user_goal.models import UserDailyGoal


@admin.register(UserDailyGoal)
class UserDailyGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'completed')
    list_select_related = ('user',)
    show_full_result_count = False
