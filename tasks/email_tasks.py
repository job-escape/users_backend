# import logging

# from account.models import CustomUser
# from jobescape.celery import app
# from shared.emailer import send_complete_registration
# from django.utils import timezone
# logger = logging.getLogger(__name__)


# @app.task(ignore_result=True)
# def delay_registration_email(user_id, cascade=1):
#     """
#         Send a "complete registration" email if the user has not completed registration at the time of execution
#     """
#     exists = CustomUser.objects.filter(id=user_id, password='', token__isnull=False).exists()
#     if exists:
#         ls = CustomUser.objects.filter(id=user_id).values_list('email', 'token')
#         email, token = ls[0]
#         send_complete_registration(user_id, email, token)
#         match cascade: 
#             case 1:
#                 delay_registration_email.apply_async(args=[user_id, 2], eta=timezone.now() + timezone.timedelta(days=1))
#             case 2: 
#                 delay_registration_email.apply_async(args=[user_id, 3], eta=timezone.now() + timezone.timedelta(days=5))
            
#         logger.debug("Email for completing regisration has been sent for user %d, email %s", user_id, email)
#         print("done")
#     else:
#         logger.debug("Email for completing regisration has been skipped for user %d", user_id)
#         print("not done")
