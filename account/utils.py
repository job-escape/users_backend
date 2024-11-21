from django.contrib.auth.models import AnonymousUser
from django.shortcuts import get_object_or_404
from rest_framework.request import Request

from account.models import GatewayChoices
from custom.custom_exceptions import BadRequest


def select_payment_system(email: str, country_code: str):
    """Initially created for AB testing, this function now is redundant. User's payment system is updated after a successful payment.

    :param email: user email
    :type email: str
    :param country_code: user's country code
    :type country_code: str
    :return: payment system
    :rtype: GatewayChoices
    """
    # TODO what to do with this?
    return GatewayChoices.PADDLE


def get_user_or_404(request: Request, queryset):
    user = request.user
    if isinstance(user, AnonymousUser):
        if email := request.data.get("email", False):  # type: ignore
            user = get_object_or_404(queryset, email__iexact=email)
        else:
            raise BadRequest("email is required.")
    return user


# def createPaddleSubscriptionManua(email, customer_id, subscription_id):
#     user, _ = CustomUser.objects.get_or_create(email=email)
#     user.set_password("BFdu7f9!DHfd8sh")
#     user.save()
#     subscription = Subscription.objects.get(name="Monthly")
#     user_subscription, _ = UserSubscription.objects.update_or_create(
#         user=user,
#         subscription=subscription,
#         defaults={
#             "expires": timezone.now() + timezone.timedelta(days=8),
#             "status": SubStatusChoices.TRIALING,
#             "paid_counter": 1
#         })
#     PaddleCustomer.objects.update_or_create(
#         user=user,
#         defaults={
#             "id": customer_id,
#         })
#     PaddleUserSubscription.objects.update_or_create(
#         user_subscription=user_subscription,
#         defaults={
#             "subscription_id": subscription_id,
#         })


# def iterateThroughExcel(file):
#     df = pd.read_excel(file)
#     for index, row in df.iterrows():
#         try:
#             createPaddleSubscriptionManua(row['email'], row['customer_id'], row['subscription_id'])
#         except:
#             print("Error ", row['email'], row['customer_id'], row['subscription_id'])


# def detectConflicts():
#     users = CustomUser.objects.exclude(password='')
#     new_users = CustomUser.objects.filter(password='')
#     emails = users.values_list('email', flat=True)
#     conflicting = []
#     copies = []
#     doppels = {}
#     to_delete = []
#     for email_i in emails:
#         email = email_i.lower()
#         if new_users.filter(email__iexact=email).exists():
#             print(f"Unregistered user found for email {email_i}")
#             conflicting.append(email_i)
#             to_delete.append(new_users.filter(email__iexact=email))
#         if doppels.get(email):
#             print(f"Similar registered account found for emails {email_i} and {doppels.get(email)}")
#             copies.append(email_i)
#         else:
#             doppels[email] = email_i
#     print("Conflicting:")
#     [print(i) for i in conflicting]
#     print("Registered copies:")
#     [print(i) for i in copies]
#     new_users.values('email').annotate(email_lower=Lower(F('email'))).annotate(email_count=Count(F('email_lower'))).filter()
#     u_conflicts = new_users.annotate(email_lower=Lower(F('email'))).values('email_lower').annotate(
#         email_count=Count('email_lower')).filter(email_count__gt=1).values_list('email_lower', flat=True)
#     u_copies = []
#     for email in u_conflicts:
#         u_copies.append(new_users.filter(email__iexact=email).values_list('pk', flat=True)[1::])
#     u_to_delete = new_users.filter(pk__in=u_copies)
#     print("Unregistered copies:")
#     [print(i) for i in u_conflicts]
#     print("done.")
#     # Run to delete:
#     # [i.delete() for i in to_delete]
#     # u_to_delete.delete()
#     # Copy conflicts should be solved individually
#     return to_delete, u_to_delete, copies


# def emailsToLower():
#     to_delete, u_to_delete, copies = detectConflicts()
#     [i.delete() for i in to_delete]
#     u_to_delete.delete()
#     if len(copies) == 0:
#         print("Copies not detected. Updating...")
#         qs = CustomUser.objects.exclude(email=Lower(F('email'))).update(email=Lower(F('email')))
#         print("Successful.")
#         return []
#     print("Copies detected. Aborting.")
#     return copies
