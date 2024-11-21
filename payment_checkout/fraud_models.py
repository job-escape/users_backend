from django.db import models


class FraudPayment(models.Model):
    email = models.CharField(verbose_name="Email")
    ip = models.CharField(verbose_name="IP")
    geo = models.CharField(verbose_name="GEO")
    fingerprint = models.CharField(verbose_name="Fingerprint")
    sub_id = models.IntegerField(verbose_name="Subscription ID")
    trial = models.CharField(verbose_name="Trial type")
    error_code = models.CharField(verbose_name="Error code", null=True, blank=True)
    datetime = models.DateTimeField(verbose_name="Date Created", auto_now_add=True)
