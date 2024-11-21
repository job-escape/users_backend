# webinars/models.py

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class WebinarStatusType(models.TextChoices):
    UPCOMING = 'upcoming', _('Upcoming')
    LIVE = 'live', _('Live')
    ENDED = 'ended', _('Ended')


class Webinar(models.Model):
    title = models.CharField(_("Title"), max_length=100, default="", blank=True)
    hoster = models.CharField(_("Hoster"), max_length=50, default="", blank=True)
    hoster_description = models.CharField(_("Hoster description"), max_length=50, default="", blank=True)
    hoster_image = models.ImageField(_("Promo image"), upload_to='webinars/hoster/', max_length=100, null=True, blank=True)
    description = models.TextField(_("Description"), default="", blank=True)
    short_description = models.TextField(_("Short Description"), default="", blank=True)
    start_datetime = models.DateTimeField(_("Start date and time"), default=timezone.now)
    end_datetime = models.DateTimeField(_("End date and time"), default=timezone.now)
    attendees = models.CharField(_("Number of attendees"), default="99+")
    duration = models.CharField(_("Duration"), max_length=10, default="1+ hour", blank=True)
    promo_image = models.ImageField(_("Promo image"), upload_to='webinars/images/', max_length=100, null=True, blank=True)
    link = models.CharField(_("Link to webinar Zoom or video recording"), max_length=250, default="", blank=True)
    status = models.CharField(_("Status"), max_length=10, default=WebinarStatusType.UPCOMING,  choices=WebinarStatusType.choices)

    class Meta:
        ordering = ['-start_datetime']

    def __str__(self):
        return f"{self._meta.model_name}[{self.pk}] {self.title}"
