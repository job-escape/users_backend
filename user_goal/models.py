# user_goal/models.py

from django.db import models
from django.utils import timezone


class UserDailyGoal(models.Model):
    user = models.ForeignKey('account.CustomUser', verbose_name="User", on_delete=models.CASCADE)
    completed = models.BooleanField(verbose_name="Is Completed?", default=False)
    date = models.DateField(default=timezone.now, verbose_name="Goal Date")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name="user-daily-goal--user-date-unique-constraint")
        ]

    def __str__(self) -> str:
        return f"{self._meta.object_name}[{self.pk}]"
