from django.utils import timezone
from django.utils.timezone import timedelta

from custom.custom_exceptions import Fraud3dsException
from payment_checkout.fraud_models import FraudPayment

force_3ds_geo = ('NA', 'MW', 'ZM', 'TZ', 'CN', 'BW', 'UZ', 'JM', 'TN', 'CM', 'YE', 'BJ', 'TJ', 'SZ',
                 'BT', 'SE', 'SR', 'HT', 'TD', 'NG', 'PK', 'SN', "GY", "SV", "CL", "BS", "CR", "HN")
force_3ds_bin = ("521729", "472409", "457896", "483561", "434769", "448387", "473702", "445143", "545756",
                 "434256", "536619", "421689", "412752", "476215", "465865", "400022", "430864", "517992")


def force_3ds_check_geo(geo: str):
    if geo in force_3ds_geo:
        raise Fraud3dsException("Forced 3DS 1")


def force_3ds_check_bin(bin: str):
    if bin in force_3ds_bin:
        raise Fraud3dsException("Forced 3DS 2")


def force_3ds_emailByCardHash(fingerprint: str):
    if FraudPayment.objects.filter(fingerprint=fingerprint, datetime__gte=timezone.now()-timedelta(hours=24)).values("email").distinct().count() > 3:
        raise Fraud3dsException("Forced 3DS 3")
    if FraudPayment.objects.filter(fingerprint=fingerprint, datetime__gte=timezone.now()-timedelta(days=7)).values("email").distinct().count() > 6:
        raise Fraud3dsException("Forced 3DS 4")


def force_3ds_cardHashByEmail(email: str):
    if FraudPayment.objects.filter(email=email, datetime__gte=timezone.now()-timedelta(minutes=30)).values("fingerprint").distinct().count() > 3:
        raise Fraud3dsException("Forced 3DS 5")
    if FraudPayment.objects.filter(email=email, datetime__gte=timezone.now()-timedelta(hours=24)).values("fingerprint").distinct().count() > 4:
        raise Fraud3dsException("Forced 3DS 6")
    if FraudPayment.objects.filter(email=email, datetime__gte=timezone.now()-timedelta(days=7)).values("fingerprint").distinct().count() > 6:
        raise Fraud3dsException("Forced 3DS 7")


def force_3ds_emailByIp(ip: str):
    if FraudPayment.objects.filter(ip=ip, datetime__gte=timezone.now()-timedelta(minutes=30)).values("email").distinct().count() > 4:
        raise Fraud3dsException("Forced 3DS 8")
    if FraudPayment.objects.filter(ip=ip, datetime__gte=timezone.now()-timedelta(hours=24)).values("email").distinct().count() > 6:
        raise Fraud3dsException("Forced 3DS 9")
    if FraudPayment.objects.filter(ip=ip, datetime__gte=timezone.now()-timedelta(days=7)).values("email").distinct().count() > 11:
        raise Fraud3dsException("Forced 3DS 10")


def force_3ds_geoByEmail(email: str):
    if FraudPayment.objects.filter(email=email, datetime__gte=timezone.now()-timedelta(minutes=30)).values("geo").distinct().count() > 3:
        raise Fraud3dsException("Forced 3DS 11")


def force_3ds_orderByEmail(email: str):
    if FraudPayment.objects.filter(email=email, error_code="20151", datetime__gte=timezone.now()-timedelta(hours=24)).count() > 2:
        raise Fraud3dsException("Forced 3DS 12")
    if FraudPayment.objects.filter(email=email, error_code="20051", datetime__gte=timezone.now()-timedelta(hours=24)).count() > 3:
        raise Fraud3dsException("Forced 3DS 13")
    if FraudPayment.objects.filter(email=email, error_code__in=['20062', '30036', '30043', '30041'], datetime__gte=timezone.now()-timedelta(days=30)).count() > 0:
        raise Fraud3dsException("Forced 3DS 14")
    if FraudPayment.objects.filter(email=email, error_code__isnull=False, datetime__gte=timezone.now()-timedelta(hours=24)).count() > 5:
        raise Fraud3dsException("Forced 3DS 15")


def force_3ds_orderByCardHash(fingerprint: str):
    if FraudPayment.objects.filter(fingerprint=fingerprint, error_code="20151", datetime__gte=timezone.now()-timedelta(hours=24)).count() > 2:
        raise Fraud3dsException("Forced 3DS 16")
    if FraudPayment.objects.filter(fingerprint=fingerprint, error_code__in=['20062', '30036', '30043', '30041'], datetime__gte=timezone.now()-timedelta(days=30)).count() > 0:
        raise Fraud3dsException("Forced 3DS 17")
