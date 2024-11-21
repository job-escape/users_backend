from django.test import TestCase

# Create your tests here.
order_webhook_email_test_request_data = {
    "order": {
        "amount": 100,
        "currency": "USD",
        "order_description": "Premium package",
        "descriptor": "google.com",
        "order_id": "",
        "processing_amount": 0,
        "processing_currency": "USD",
        "refunded_amount": 0,
        "status": "approved",
        "subscription_id": "4be82611-2a95-44b0-a80e-87700cbfd58a",
        "marketing_amount": 0,
        "marketing_currency": "USD",
        "traffic_source": "facebook",
        "customer_email": "olzhas.pub@gmail.com"
    },
    "transaction": {
        "descriptor": "google.com",
        "amount": 100,
        "card": {
            "bank": "JSC UNIVERSAL BANK",
            "bin": "444111",
            "brand": "VISA",
            "card_exp_month": "12",
            "card_exp_year": 2028,
            "card_holder": "John Snow",
            "card_type": "CREDIT",
            "card_id": "22733af4-f6c6-4368-b7d0-98aeb0253a57",
            "country": "USA",
            "number": "444111XXXXXX9435"
        },
        "card_token": {
            "token": "baf2ff5c5a125aeabb4b80d7b983f66f3abf5dbb8d939df48b40755674eddceee78084eab5fa9c15a339c94f1ad2b30cf299"
        },
        "created_at": "2022-12-27 11:45:30",
        "currency": "USD",
        "id": "5019d00bb70f82cd42f6bc654cbdfcbd63a9b5b1dbd6a",
        "operation": "pay",
        "status": "approved",
        "updated_at": "2022-12-28 11:45:30",
        "refund_reason": "Solidgate - Issuer Fraud Notification",
        "refund_reason_code": "0022",
        "billing_details": {
            "address": "21 Bedford Ave",
            "city": "Boston",
            "country": "USA",
            "state": "NY",
            "zip": "91191"
        },
        "error": {
            "code": "3.12",
            "messages": "Closed User Account",
            "merchant_advice_code": "21"
        }
    }
}
