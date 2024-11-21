import json
import logging
from datetime import datetime, timedelta
from typing import Literal

import mailerlite as MailerLite
import requests
from django.conf import settings
from django.utils import timezone

from account.models import CustomUser
# from users.celery import app
from web_analytics.event_manager import EventManager

mailerlite_client = MailerLite.Client({
    'api_key': settings.MAILERLITE_API_KEY
})
# return send_mail(
#     "Subject here",
#     "Here is the message.",
#     "error@myjobescape.com",
#     ["olzhas.pub@gmail.com"],
#     fail_silently=False,
# )


def send_template_email(email: str, template_id: int, full_name: str | None, email_theme: str = '(some)', is_task: bool = False, **variables):
    logger = logging.getLogger('tasks' if is_task else None)
    variables.update({
        "name": full_name,
        "email": email,
    })
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": settings.PM_API_SECRET
    }
    data = {
        "TemplateId": template_id,
        "TemplateModel": variables,
        "From": "support@jobescape.me",
        "To": email,
        "Tag": email_theme,
    }
    res: requests.Response = requests.post(
        "https://api.postmarkapp.com/email/withTemplate",
        json=data,
        headers=headers,
        timeout=settings.REQUESTS_TIMEOUT
    )
    if res.status_code == 200:
        logger.info("Successfully sent %s to address=%s.", email_theme, email)
    elif res.status_code == 422:
        try:
            logger.warning("Failed to send %s to email=%s with response=%s; status=%d; \ndata=%s", email_theme,
                           email, json.dumps(res.json(), indent=2), res.status_code, json.dumps(data, indent=2))
        except requests.exceptions.JSONDecodeError:
            logger.warning("Failed to send %s to email=%s with no response; status=%d; \ndata=%s", email_theme,
                           email, res.status_code, json.dumps(data, indent=2))
    else:
        try:
            logger.error("Failed to send %s to email=%s with response=%s; status=%d; \ndata=%s", email_theme,
                         email, json.dumps(res.json(), indent=2), res.status_code, json.dumps(data, indent=2))
        except requests.exceptions.JSONDecodeError:
            logger.error("Failed to send %s to email=%s with no response; status=%d; \ndata=%s", email_theme,
                         email, res.status_code, json.dumps(data, indent=2))
    # data = {
    #     'subject': subject,
    #     'from': {'name': 'Mark from Jobescape', 'email': 'contact@myjobescape.com'},
    #     'to': [
    #         {'name': f"{name} {surname if surname else ''}", 'email': email}
    #     ],
    #     "template": {
    #         'id': template_id,  # ID of the template uploaded in the service. Use this
    #         # (https://sendpulse.com/integrations/api/bulk-email#template-list)
    #         # method to get the template ID (use either real_id or id parameter from the reply)
    #         'variables': variables
    #     },
    # }
    # res = SPApiProxy.smtp_send_mail_with_template(data)
    # with contextlib.suppress(Exception):
    #     if res["data"]["is_error"]:  # type: ignore
    #         logging.error("Failed to send %s to email=%s with response=%s;\ndata=%s", email_theme,
    #                       email, json.dumps(res['data'], indent=2), json.dumps(data, indent=2))
    #     else:
    #         logging.info("Successfully sent %s to address=%s.", email_theme, email)
    return res


def send_password_code(user_id: int, full_name: str, email: str, code: str):
    EventManager().sendEvent("pr_webapp_email_password_change_sent", user_id, topic="app")
    return send_template_email(
        email,
        35608585,
        full_name,
        email_theme='password reset code',
        code=code
    )


def send_complete_registration(user_id: int, email: str, token: str):
    EventManager().sendEvent("pr_webapp_email_complete_registration_sent", user_id, topic="app")
    return send_template_email(
        email,
        35608712,
        None,
        email_theme='complete registration',
        token=token,
        id=user_id
    )

def send_upsell(user_id: int, email: str, template: int):
    EventManager().sendEvent("pr_webapp_email_upsell_sent", user_id, topic="funnel")
    return send_template_email(
        email,
        template,
        None,
        email_theme='Your  "ChatGPT Pro" Library is here!',
        id=user_id
    )


# @app.task(ignore_result=True)
def send_welcome(user_id: int, email: str):
    EventManager().sendEvent("pr_webapp_email_welcome_sent", user_id, topic="app")
    return send_template_email(
        email,
        35698437,
        None,
        email_theme='welcome',
        is_task=True
    )


# @app.task(ignore_result=True)
# def send_personal_plan(user_id: int, email: str):
#     purchased = UserSubscription.objects.filter(user__id=user_id).exclude(status=SubStatusChoices.INACTIVE).exists()
#     if purchased:
#         vals = CustomUser.objects.filter(pk=user_id).values('full_name').first()
#         if vals:
#             name = vals['full_name']
#         else:
#             return False
#         EventManager().sendEvent(
#             "pr_webapp_email_personal_plan_sent",
#             user_id,
#             {"purchase": "post", },
#             amplitude=False,
#             topic="app"
#         )
#         return send_personal_plan_post(email, name)
#     else:
#         EventManager().sendEvent(
#             "pr_webapp_email_personal_plan_sent",
#             user_id,
#             {"purchase": "pre", },
#             amplitude=False,
#             topic="app"
#         )
#         return send_personal_plan_pre(email)


# def send_personal_plan_post(email: str, full_name: str):
#     return send_template_email(
#         email,
#         35992915,
#         full_name,
#         'personal plan post',
#         True,
#     )


# def send_personal_plan_pre(email: str):
    # return send_template_email(
    #     email,
    #     36002125,
    #     None,
    #     'personal plan pre',
    #     True,
    # )


# @app.task(ignore_result=True)
# def send_personal_plan_clean(user_id: int, email: str, data: dict):
#     purchased = UserSubscription.objects.filter(user__id=user_id).exclude(status=SubStatusChoices.INACTIVE).exists()
#     prop = "post" if purchased else "pre"
#     EventManager().sendEvent(
#         "pr_webapp_email_personal_plan_sent",
#         user_id,
#         {"ab_test_14_re": "clean", "purchase": prop, "$set_once": {"ab_test_14_re": "clean"}},
#         False
#     )
#     desired_income = data.get('desired_income', 'More than 250,000')
#     if desired_income == "50,000-100,000 USD":
#         desired_income = "100,000 USD"
#         desired_income_monthly = "8,500 USD"
#     elif desired_income == "100,000-250,000 USD":
#         desired_income = "250,000 USD"
#         desired_income_monthly = "21,100 USD"
#     else:
#         desired_income = "350,000 USD"
#         desired_income_monthly = "30,000 USD"
#     age = data.get('age', '18-25')
#     gender = data.get('gender', 'Male')
#     goal = data.get('goal', 'Launch an online business')
#     if isinstance(age, dict):
#         age = age.get('value')
#     if isinstance(gender, dict):
#         gender = gender.get('value')
#     if isinstance(goal, dict):
#         goal = goal.get('value')

#     variables = {
#         'age': age,
#         'gender': gender,
#         'goal': goal,
#         'exp_marketing': data.get('exp_marketing', 'Beginner'),
#         'channel': data.get('channel', 'Social media marketing'),
#         'desired_income': desired_income,
#         'desired_income_monthly': desired_income_monthly,
#     }
#     return send_template_email(
#         email,
#         35698572,
#         None,
#         'personal plan',
#         **variables
#     )


# @app.task(ignore_result=True)
def send_farewell_email(user_id: int, email: str, full_name: str, sub_status: Literal['trial', 'subscription'], exp_date: timezone.datetime, plan: str):
    EventManager().sendEvent(
        "pr_webapp_unsubscribed_email_sent",
        user_id,
        topic="app",
    )
    return send_template_email(
        email,
        36175373,
        full_name,
        'farewell',
        status=sub_status,
        date=exp_date,
        plan=plan
    )


def funnel_info_mailerlite(funnel_info):
    try:
        duration = datetime.today()+timedelta(days=30)
        money_plan = None
        specific_reason = None
        if 'money_plan' in funnel_info:
            money_plan = funnel_info['money_plan']['value']
            if funnel_info['money_plan']['value'] == "$2001 - $5000":
                duration = datetime.today()+timedelta(days=60)
            elif funnel_info['money_plan']['value'] == "$5001 - $10000":
                duration = datetime.today()+timedelta(days=90)
            elif funnel_info['money_plan']['value'] == "More than $10000":
                duration = datetime.today()+timedelta(days=90)
        if 'vacation' in funnel_info:
            if not funnel_info['vacation']['value'] == 'Other':
                specific_reason = funnel_info['vacation']['value']
        return {
            "specific_reason": specific_reason,
            "money_plan": money_plan,
            "duration_plan": duration.strftime("%d %B")
        }
    except:
        logging.warning("emailer: failed to create fields in addressbook: %s\n", json.dumps(funnel_info, indent=2))
        return {}


def add_to_addressbook(email, funnel_info):
    data = funnel_info_mailerlite(funnel_info)
    try:
        res: dict = mailerlite_client.subscribers.create(email, fields=data, groups=["124733726756177359"])
        if "errors" in res:
            logging.warning("emailer: failed to add %s to addressbook: %s\n", email, res)
            return
        logging.info("emailer: successfully added to addressbook. email=%s", email)
    except Exception as e:
        logging.warning("emailer: failed to add %s to addressbook due to exception %s", email, str(e))


def update_addressbook(email, data):
    try:
        res: dict = mailerlite_client.subscribers.update(email, groups=["124733726756177359"], fields=data)
        if "errors" in res:
            logging.warning("emailer: failed to update user %s in addressbook: %s\n", email, res)
            return
        logging.info("emailer: successfully updated to addressbook. email=%s", email)
    except Exception as e:
        logging.warning("emailer: failed to update user %s in addressbook due to exception %s", email, str(e))


def remove_from_addressbook(email: str):
    try:
        res: dict = mailerlite_client.subscribers.get(email)
        if "data" in res:
            sub_id = res['data']['id']
            result = mailerlite_client.subscribers.unassign_subscriber_from_group(int(sub_id), 124733726756177359)
            if not result:
                logging.warning("emailer: failed to delete from addressbook. email=%s", email)
    except Exception as e:
        logging.warning("emailer: failed to delete from addressbook due to exception %s. email=%s", str(e), email)


def assign_to_group(email, group_id: int | str, data: dict):
    try:
        res: dict = mailerlite_client.subscribers.update(email, groups=[group_id], fields=data)
        if "errors" in res:
            logging.warning("emailer: failed to assign user %s to a group: %s\n", email, json.dumps(res, indent=2))
            return
        logging.info("emailer: successfully assigned user to a group. email=%s", email)
    except Exception as e:
        logging.warning("emailer: failed to assign user to a group due to exception %s. email=%s", str(e), email)
