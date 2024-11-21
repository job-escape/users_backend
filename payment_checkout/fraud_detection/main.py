from growthbook import GrowthBook

from account.models import GatewayChoices
from custom.custom_exceptions import Fraud3dsException, FraudRejectException
from payment_checkout.fraud_detection.force_3ds import (
    force_3ds_cardHashByEmail, force_3ds_check_bin, force_3ds_check_geo,
    force_3ds_emailByCardHash, force_3ds_emailByIp, force_3ds_geoByEmail,
    force_3ds_orderByCardHash, force_3ds_orderByEmail)
from payment_checkout.fraud_detection.rejects import (reject_cardHashByEmail,
                                                      reject_check_bin,
                                                      reject_check_geo,
                                                      reject_emailByCardHash,
                                                      reject_orderByCardHash,
                                                      reject_orderByEmail)
from payment_checkout.fraud_models import FraudPayment
from web_analytics.event_manager import EventManager

check_3ds_codes = ['20001', '20002', '20005', '20012', '20038', '20046', '20057', '20059', '20062', '20063', '20064',
                   '20065', '20075', '20078', '20081', '20093', '20108', '20151', '20152', '20154', '20155', '20182', '20183']


_EVENT_MANAGER = EventManager(GatewayChoices.CHECKOUT)


def check(user_id: int, fingerprint: str, email: str, ip: str, geo: str, sub_id: int, trial: str, card_bin: str, gb: GrowthBook):
    """Util function to check fraud and force 3DS or reject payment attempts."""
    fraud_payment = FraudPayment.objects.create(
        fingerprint=fingerprint,
        email=email,
        ip=ip,
        geo=geo,
        sub_id=sub_id,
        trial=trial
    )
    event_data: dict[str, str | dict] = {
        "result": "OK",
        "fingerprint": fingerprint,
        "ip": ip,
        "geo": geo
    }
    try:
        reject_check_geo(geo)
        reject_cardHashByEmail(email)
        reject_orderByEmail(email)
        reject_emailByCardHash(fingerprint)
        reject_orderByCardHash(fingerprint)
        reject_check_bin(card_bin)

        force_3ds_check_geo(geo)
        force_3ds_check_bin(card_bin)
        force_3ds_cardHashByEmail(email)
        force_3ds_emailByCardHash(fingerprint)
        force_3ds_orderByCardHash(fingerprint)
        force_3ds_orderByEmail(email)
        force_3ds_emailByIp(ip)
        force_3ds_geoByEmail(email)
    except FraudRejectException as e:
        event_data["message"] = str(e)
        event_data["result"] = "REJECT"
        _EVENT_MANAGER.sendEvent("pr_funnel_middleware", user_id, event_data, topic="funnel")
        return "REJECT", str(e), fraud_payment
    except Fraud3dsException as e:
        event_data["message"] = str(e)
        event_data["result"] = "FORCE_3DS"
        _EVENT_MANAGER.sendEvent("pr_funnel_middleware", user_id, event_data, topic="funnel")
        return "FORCE_3DS", None, fraud_payment

    _EVENT_MANAGER.sendEvent("pr_funnel_middleware", user_id, event_data, topic="funnel")
    return "OK", None, fraud_payment
