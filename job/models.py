# job/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from account.models import CustomUser


class Company(models.Model):
    name = models.CharField(_("Name"), max_length=100, default="", blank=True)
    description = models.CharField(_("Name"), max_length=250, default="", blank=True)
    employees = models.CharField(_("Number of employees"), max_length=10, default="", blank=True)
    platform = models.CharField(_("Platform"), max_length=30, default="", blank=True)
    link = models.CharField(_("Link to website"), max_length=250, default="", blank=True)

    def __str__(self):
        return f"{self._meta.model_name}[{self.pk}] {self.name}"


class Job(models.Model):
    title = models.CharField(_("Title"), max_length=100, default="", blank=True)
    company = models.ForeignKey(Company, verbose_name=_("Company"), related_name="jobs", on_delete=models.CASCADE)
    content = models.TextField(_("Content"), default="", blank=True)
    date_modified = models.DateTimeField(_("Date modified"), auto_now=True)
    format = models.CharField(_("Format of job"), default="Remote", blank=True)
    location = models.CharField(_("Location of job"), default="Anywhere", blank=True)
    employment = models.CharField(_("Type of employment"), default="Part-Time", blank=True)
    salary = models.CharField(_("Salary"), default="$15 000 - $25 000", blank=True)
    link = models.CharField(_("Apply now link"), max_length=250, default="", blank=True)
    expired = models.BooleanField(_("Expired?"), default=False)
    expiration_reason = models.CharField(_("Expiration reason"), max_length=500, default="", blank=True)
    similar_jobs = models.ManyToManyField("self", verbose_name=_("Similar jobs"), blank=True)
    img = models.ImageField(_("Image"), upload_to='job/', null=True, blank=True)

    class Meta:
        ordering = ['-date_modified']

    def __str__(self):
        return f"{self._meta.model_name}[{self.pk}] {self.title}"


class JobUser(models.Model):
    user = models.ForeignKey(CustomUser, verbose_name=_("User"), related_name="jobusers", on_delete=models.CASCADE)
    job = models.ForeignKey(Job, verbose_name=_("Job"), on_delete=models.CASCADE)
    date_created = models.DateTimeField(_("Date created"), auto_now=True)

    class Meta:
        ordering = ['-date_created']
        constraints = [
            models.UniqueConstraint(fields=['user', 'job'], name="jobuser--job-user-unique-constraint")
        ]

    def __str__(self):
        return f"{self._meta.model_name}[{self.pk}] {self.job.title} - {self.user.email}"
