import logging
import uuid

from django.db.models import Q

from custom.custom_exceptions import BadRequest, InternalServerError
from payment_solidgate.models import SolidgateSubscription
from subscription.models import TrialPriceChoices


def get_payment_intent(intent_data: dict, user_id, email: str, product_id: str):
    zip_code = intent_data.pop('zip_code')
    intent = {
        "order_id": str(uuid.uuid4()),
        "order_description": "Jobescape Subscription",
        "product_id": product_id,
        "customer_account_id": str(user_id),
        "customer_email": email,
        "settle_interval": 0,
        "type": "auth",
        "billing_address": {
            "zip_code": zip_code
        },
    }
    intent.update(intent_data)
    return intent


def get_partial_payment_intent(intent_data: dict, product_id: str):
    intent = {
        "product_id": product_id,
        "order_description": "Jobescape Subscription",
    }
    intent.update(intent_data)
    return intent


def get_paypal_init(email: str, ip: str, order_id: str, product_id: str, user_id: int):
    init = {
        "payment_method": "paypal-vault",
        "order_id": order_id,
        "order_description": "Jobescape Subscription",
        "customer_email": email,
        "ip_address": ip,
        "platform": "WEB",
        "product_id": product_id,
        "customer_account_id": str(user_id),
    }
    return init


def get_solidgate_subscription_from_sg_sub_id(sg_sub_id: str) -> SolidgateSubscription:
    """Get SolidgateSubscription instance from Solidgate's internal subscription id

    :param sg_sub_id: _description_
    :type sg_sub_id: str
    :raises InternalServerError: Found multiple Solidgate subscription intances for the given sub_id!
    :raises InternalServerError: Solidgate subscription intances not found for the given sub_id!
    :return: _description_
    :rtype: SolidgateSubscription
    """
    qs = SolidgateSubscription.objects.filter(
        Q(trial_timeout_subscription_id=sg_sub_id) |
        Q(trial_standard_subscription_id=sg_sub_id) |
        Q(trial_chase_subscription_id=sg_sub_id)
    )
    if qs.count() > 1:
        logging.error("Solidgate: Found multiple Solidgate subscription intances for the given sg_sub_id! sg_sub_id=%s", sg_sub_id)
        raise InternalServerError("Solidgate: Found multiple Solidgate subscription intances for the given sg_sub_id!")
    if qs.count() == 0:
        logging.error("Solidgate: Solidgate subscription intances not found for the given sg_sub_id! sg_sub_id=%s", sg_sub_id)
        raise InternalServerError("Solidgate: Solidgate subscription intances not found for the given sg_sub_id!")
    return qs.select_related('subscription').first()  # type: ignore


def get_product_id_from_trial_type(sg_sub: SolidgateSubscription, trial_type: str):
    match trial_type:  # ? OR API GATEWAY func
        case TrialPriceChoices.STANDARD:
            return sg_sub.trial_standard_subscription_id
        case TrialPriceChoices.CHASE:
            return sg_sub.trial_chase_subscription_id
        case TrialPriceChoices.TIMEOUT:
            return sg_sub.trial_timeout_subscription_id
        case _:  # Technically impossible to reach this if serializer is correct.
            raise BadRequest('Invalid trial type.')


COUNTRY_CODES_MAPPING = {
    "AFG": "AF", "ALB": "AL", "DZA": "DZ", "ASM": "AS", "AND": "AD", "AGO": "AO", "AIA": "AI",
    "ATA": "AQ", "ATG": "AG", "ARG": "AR", "ARM": "AM", "ABW": "AW", "AUS": "AU", "AUT": "AT",
    "AZE": "AZ", "BHS": "BS", "BHR": "BH", "BGD": "BD", "BRB": "BB", "BLR": "BY", "BEL": "BE",
    "BLZ": "BZ", "BEN": "BJ", "BMU": "BM", "BTN": "BT", "BOL": "BO", "BES": "BQ", "BIH": "BA",
    "BWA": "BW", "BVT": "BV", "BRA": "BR", "IOT": "IO", "BRN": "BN", "BGR": "BG", "BFA": "BF",
    "BDI": "BI", "CPV": "CV", "KHM": "KH", "CMR": "CM", "CAN": "CA", "CYM": "KY", "CAF": "CF",
    "TCD": "TD", "CHL": "CL", "CHN": "CN", "CXR": "CX", "CCK": "CC", "COL": "CO", "COM": "KM",
    "COD": "CD", "COG": "CG", "COK": "CK", "CRI": "CR", "HRV": "HR", "CUB": "CU", "CUW": "CW",
    "CYP": "CY", "CZE": "CZ", "CIV": "CI", "DNK": "DK", "DJI": "DJ", "DMA": "DM", "DOM": "DO",
    "ECU": "EC", "EGY": "EG", "SLV": "SV", "GNQ": "GQ", "ERI": "ER", "EST": "EE", "SWZ": "SZ",
    "ETH": "ET", "FLK": "FK", "FRO": "FO", "FJI": "FJ", "FIN": "FI", "FRA": "FR", "GUF": "GF",
    "PYF": "PF", "ATF": "TF", "GAB": "GA", "GMB": "GM", "GEO": "GE", "DEU": "DE", "GHA": "GH",
    "GIB": "GI", "GRC": "GR", "GRL": "GL", "GRD": "GD", "GLP": "GP", "GUM": "GU", "GTM": "GT",
    "GGY": "GG", "GIN": "GN", "GNB": "GW", "GUY": "GY", "HTI": "HT", "HMD": "HM", "VAT": "VA",
    "HND": "HN", "HKG": "HK", "HUN": "HU", "ISL": "IS", "IND": "IN", "IDN": "ID", "IRN": "IR",
    "IRQ": "IQ", "IRL": "IE", "IMN": "IM", "ISR": "IL", "ITA": "IT", "JAM": "JM", "JPN": "JP",
    "JEY": "JE", "JOR": "JO", "KAZ": "KZ", "KEN": "KE", "KIR": "KI", "PRK": "KP", "KOR": "KR",
    "KWT": "KW", "KGZ": "KG", "LAO": "LA", "LVA": "LV", "LBN": "LB", "LSO": "LS", "LBR": "LR",
    "LBY": "LY", "LIE": "LI", "LTU": "LT", "LUX": "LU", "MAC": "MO", "MDG": "MG", "MWI": "MW",
    "MYS": "MY", "MDV": "MV", "MLI": "ML", "MLT": "MT", "MHL": "MH", "MTQ": "MQ", "MRT": "MR",
    "MUS": "MU", "MYT": "YT", "MEX": "MX", "FSM": "FM", "MDA": "MD", "MCO": "MC", "MNG": "MN",
    "MNE": "ME", "MSR": "MS", "MAR": "MA", "MOZ": "MZ", "MMR": "MM", "NAM": "NA", "NRU": "NR",
    "NPL": "NP", "NLD": "NL", "NCL": "NC", "NZL": "NZ", "NIC": "NI", "NER": "NE", "NGA": "NG",
    "NIU": "NU", "NFK": "NF", "MNP": "MP", "NOR": "NO", "OMN": "OM", "PAK": "PK", "PLW": "PW",
    "PSE": "PS", "PAN": "PA", "PNG": "PG", "PRY": "PY", "PER": "PE", "PHL": "PH", "PCN": "PN",
    "POL": "PL", "PRT": "PT", "PRI": "PR", "QAT": "QA", "MKD": "MK", "ROU": "RO", "RUS": "RU",
    "RWA": "RW", "REU": "RE", "BLM": "BL", "SHN": "SH", "KNA": "KN", "LCA": "LC", "MAF": "MF",
    "SPM": "PM", "VCT": "VC", "WSM": "WS", "SMR": "SM", "STP": "ST", "SAU": "SA", "SEN": "SN",
    "SRB": "RS", "SYC": "SC", "SLE": "SL", "SGP": "SG", "SXM": "SX", "SVK": "SK", "SVN": "SI",
    "SLB": "SB", "SOM": "SO", "ZAF": "ZA", "SGS": "GS", "SSD": "SS", "ESP": "ES", "LKA": "LK",
    "SDN": "SD", "SUR": "SR", "SJM": "SJ", "SWE": "SE", "CHE": "CH", "SYR": "SY", "TWN": "TW",
    "TJK": "TJ", "TZA": "TZ", "THA": "TH", "TLS": "TL", "TGO": "TG", "TKL": "TK", "TON": "TO",
    "TTO": "TT", "TUN": "TN", "TUR": "TR", "TKM": "TM", "TCA": "TC", "TUV": "TV", "UGA": "UG",
    "UKR": "UA", "ARE": "AE", "GBR": "GB", "UMI": "UM", "USA": "US", "URY": "UY", "UZB": "UZ",
    "VUT": "VU", "VEN": "VE", "VNM": "VN", "VGB": "VG", "VIR": "VI", "WLF": "WF", "ESH": "EH",
    "YEM": "YE", "ZMB": "ZM", "ZWE": "ZW", "ALA": "AX",
}

SOLIDGATE_STATUS_MSG = {
    "0.01": "General decline",
    "0.02": "Order expired",
    "0.03": "Illegal operation (violation of law)",
    "1.01": "Authentication failed",
    "2.01": "Invalid Data/Order not found",
    "2.02": "Invalid Amount",
    "2.03": "Invalid Currency",
    "2.05": "Order not found",
    "2.06": "Invalid CVV2 code",
    "2.07": "Request Is empty",
    "2.08": "Invalid card number",
    "2.09": "Invalid expiration date",
    "2.10": "Invalid 3DS flow on the merchant side",
    "2.11": "Invalid 3DS flow on the bank side",
    "2.12": "Invalid 3DS flow",
    "2.13": "Invalid IP",
    "2.14": "Subscription error",
    "2.15": "SCA require 3D authentication",
    "2.16": "Subscription is locked",
    "2.17": "Coupon is not active",
    "3.01": "Card is blocked",
    "3.02": "Insufficient funds",
    "3.03": "Payment amount limit excess",
    "3.04": "The transaction is declined by the issuer",
    "3.05": "Call your bank",
    "3.06": "Debit card not supported",
    "3.07": "Card brand is not supported",
    "3.08": "Do not honor",
    "3.09": "3D-Secure authentication required",
    "3.10": "Suspected Fraud",
    "3.11": "Recurring payment cancelled",
    "3.12": "Closed User Account",
    "4.01": "Card is in a black list",
    "4.02": "Stolen card",
    "4.03": "Restricted card",
    "4.04": "Lost card",
    "4.05": "PSP antifraud",
    "4.06": "Blocked by Country/IP",
    "4.07": "Trusted antifraud system",
    "4.08": "AVS mismatch",
    "4.09": "Antifraud service",
    "5.01": "3D secure verification failed",
    "5.02": "Invalid Card Token",
    "5.03": "Application error",
    "5.04": "Merchant is not configured correctly",
    "5.05": "Merchant is not activated yet",
    "5.06": "Duplicate order",
    "5.07": "Exceeded API calls limits",
    "5.08": "Invalid transaction",
    "5.09": "Merchant not found",
    "5.10": "Processor does not support requested API method",
    "5.11": "Invalid routing",
    "5.12": "Account is blocked",
    "6.01": "Unknown decline code",
    "6.02": "Connection error",
    "6.03": "Processing issue",
    "7.01": "Card token not found",
    "7.02": "Google payment error",
    "7.03": "Smart cascade decline",
    "7.04": "3DS cascade to 2D",
    "7.05": "Apple online payment error",
    "7.06": "Token generation error",
    "7.07": "SCA engine error",
}


def map_subscription_id(amount):
    if amount in [515, 693]:
        return 2
    if amount in [1519, 1129]:
        return 3
    return 4


# def send_paycheck_email_util(user_sub: UserSubscription, order_data: dict, transaction_data: dict, is_renewal: bool = True):
#     '''Returns `True` if email was successfully sent and `False` otherwise'''
#     def get_date_string(date: str):
#         return datetime.strptime(date, "%Y-%m-%d %H:%M:%S").date().strftime("%Y-%m-%d")
#     assert user_sub.user, "?!"
#     assert user_sub.subscription, "?!"
#     sub = user_sub.subscription
#     user = user_sub.user
#     res = SolidgateAPI().get_subscription_status(order_data['subscription_id'])
#     data = res.json()
#     if res.status_code != status.HTTP_200_OK:
#         logging.warning("Solidgate responded with an invalid code on subscription. Data=%s", json.dumps(data, indent=2))
#         return False
#     sub_data = data['subscription']
#     func = send_renewal_paid_email if is_renewal else send_trial_paid_email
#     # Safe check for sandbox environment
#     card_brand = transaction_data['card']['brand'] if transaction_data.get('card') and transaction_data['card'].get('brand') else 'Unknown'
#     card_digits = transaction_data['card']['number'][-4:] if transaction_data.get('card') and transaction_data['card'].get('number') else 'Unknown'
#     trial_price = str(order_data['amount'])[:-2] + '.' + str(order_data['amount'])[-2:]
#     res2 = func(
#         user.first_name,
#         user.last_name,
#         user.email if not user.payment_email else user.payment_email,
#         purchase_date=get_date_string(transaction_data['updated_at']),
#         trial_price=trial_price,
#         trial_currency=order_data['currency'],
#         trial_frequency=sub.trial_cycle_frequency,
#         trial_interval=sub.trial_period_interval + ('s' if sub.trial_cycle_frequency > 1 else ''),
#         trial_start_date=get_date_string(sub_data['started_at']),
#         subscription_frequency=sub.billing_cycle_frequency,
#         subscription_interval=sub.billing_cycle_interval + ('s' if sub.billing_cycle_frequency > 1 else ''),
#         subscription_price=sub.price_amount,
#         subscription_currency=sub.price_currency,
#         next_charge_date=get_date_string(sub_data['next_charge_at']) if 'next_charge_at' in sub_data else '-',
#         card_brand=card_brand,
#         card_digits=card_digits
#     )
#     return not res2.get('data', {}).get('is_error', False)  # type: ignore
