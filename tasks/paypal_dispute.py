# import base64
# import hashlib
# import hmac
# import json
# from datetime import datetime, timedelta

# import requests
# from django.conf import settings

# # from jobescape.celery import app
# from payment_solidgate.models import PaypalDispute


# @app.task(ignore_result=True)
# def run_paypal_dispute():
#     data = {
#         "date_from": (datetime.now()-timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"),
#         "date_to": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "limit": 2000
#     }
#     encrypto_data = (settings.SOLIDGATE_API_KEY + json.dumps(data) + settings.SOLIDGATE_API_KEY).encode('utf-8')
#     sign = hmac.new(settings.SOLIDGATE_API_SECRET.encode('utf-8'), encrypto_data, hashlib.sha512).hexdigest()
#     signature = base64.b64encode(sign.encode('utf-8')).decode('utf-8')
#     headers = {'Content-Type': 'application/json',
#                'Accept': 'application/json',
#                'Merchant': settings.SOLIDGATE_API_KEY,
#                'Signature': signature}
#     res = requests.post("https://reports.solidgate.com/api/v1/apm-orders/paypal-disputes", headers=headers, json=data, timeout=15)
#     data = res.json()
#     for dispute in data['disputes']:
#         PaypalDispute.objects.get_or_create(dispute_id=dispute['dispute_id'], amount=dispute['dispute_amount'], order_id=dispute['order_id'])
#     for dispute in PaypalDispute.objects.filter(refunded=False):
#         data = {
#             "order_id": dispute.order_id,
#             "amount": dispute.amount,
#             "refund_reason_code": "0021"
#         }
#         encrypto_data = (settings.SOLIDGATE_API_KEY + json.dumps(data) + settings.SOLIDGATE_API_KEY).encode('utf-8')
#         sign = hmac.new(settings.SOLIDGATE_API_SECRET.encode('utf-8'), encrypto_data, hashlib.sha512).hexdigest()
#         signature = base64.b64encode(sign.encode('utf-8')).decode('utf-8')
#         headers = {'Content-Type': 'application/json',
#                    'Accept': 'application/json',
#                    'Merchant': settings.SOLIDGATE_API_KEY,
#                    'Signature': signature}
#         res = requests.post("https://gate.solidgate.com/api/v1/refund", headers=headers, json=data, timeout=15)
#         data = res.json()
#         if res.status_code == 200:
#             dispute.refunded = True
#             dispute.save()
