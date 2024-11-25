from google.cloud import tasks_v2
import json
import logging
from django.conf import settings
from web_analytics.event_manager import EventManager
from datetime import date, datetime
from shared.emailer import send_template_email
from web_analytics.tasks import publishMessage
from account.models import CustomUser
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from drf_spectacular.utils import extend_schema
from django.utils import timezone
from web_analytics.pubsub import EventRawSerializer, PaymentsSerializer
from typing import Any, Literal
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from google.protobuf.timestamp_pb2 import Timestamp
from shared.emailer import send_complete_registration

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


# 1st TASK
def create_send_welcome_task(user_id, user_email):
    client = tasks_v2.CloudTasksClient()
    if settings.STAGE:
        queue = settings.STAGE_QUEUE_SEND_WELCOME
        url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/send_welcome/"
    else:
        queue = settings.PROD_QUEUE_SEND_WELCOME
        url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/send_welcome/"
    parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)
    
    payload = {
        "user_id": user_id,
        "user_email": user_email
    }

    try:
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.PATCH,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            }
        }

        client.create_task(parent=parent, task=task)
        logging.debug(f"Created task create_send_welcome_task for {user_email}")
    except Exception as e:
        logging.error(f"Failed to create create_send_welcome_task: {e}")
        raise


# 1st TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def send_welcome_task_view(request):
    try:
        payload = request.data
        user_id = payload.get("user_id")
        email = payload.get("user_email")

        if not user_id or not email:
            logging.warning("Missing required fields: user_id, email in send_welcome_task_view")
            return Response(status=400)

        EventManager().sendEvent("pr_webapp_email_welcome_sent", user_id, topic="app")
        send_template_email(
            email,
            35698437,
            None,
            email_theme='welcome',
            is_task=True
        )

        logging.debug(f"Welcome email successfully sent to user_id={user_id}, email={email}")
        return Response(status=200)

    except Exception as e:
        logging.error(f"Error processing send_welcome task: {e}")
        return Response(status=500)


# 2nd TASK
def create_delay_registration_email_task(user_id, cascade, delay_minutes=0, delay_days=0):
    """Creates a delayed task for sending a complete registration email."""
    try:
        client = tasks_v2.CloudTasksClient()

        if settings.STAGE:
            queue = settings.STAGE_QUEUE_DELAY_EMAIL
            url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/delay_registration_email/"
        else:
            queue = settings.PROD_QUEUE_DELAY_EMAIL
            url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/delay_registration_email/"

        parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)

        payload = {
            "user_id": user_id,
            "cascade": cascade,
        }

        schedule_time = timezone.now() + timezone.timedelta(minutes=delay_minutes, days=delay_days)
        timestamp = Timestamp()
        timestamp.FromDatetime(schedule_time)

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            },
            "schedule_time": timestamp,
        }

        response = client.create_task(parent=parent, task=task)
        logging.debug(f"Created task: {response.name} for user {user_id}, cascade {cascade} with delay {delay_minutes} minutes and {delay_days} days")

    except Exception as e:
        logging.error(f"Failed to create Cloud Task: {e}")
        raise


# 2nd TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def delay_registration_email_view(request):
    """Handles delayed registration email tasks."""
    try:
        payload = request.data
        user_id = payload.get("user_id")
        cascade = payload.get("cascade", 1)

        if not user_id:
            logging.warning("Missing required fields: user_id in delay_registration_email_view")
            return Response(status=400)

        exists = CustomUser.objects.filter(id=user_id, password='', token__isnull=False).exists()
        if exists:
            ls = CustomUser.objects.filter(id=user_id).values_list('email', 'token')
            email, token = ls[0]

            send_complete_registration(user_id, email, token)

            match cascade:
                case 1:
                    create_delay_registration_email_task(user_id, cascade=2, delay_minutes=0, delay_days=1)  # Next task in 1 day
                case 2:
                    create_delay_registration_email_task(user_id, cascade=3, delay_minutes=0, delay_days=5)  # Next task in 5 days

            logging.debug("Email for completing registration has been sent for user %d, email %s", user_id, email)
            return Response(status=200)
        else:
            logging.debug("Email for completing registration has been skipped for user %d", user_id)
            return Response(status=200)

    except Exception as e:
        logging.error(f"Error processing delay_registration_email task: {e}")
        return Response(status=500)

# 3rd TASK
def create_send_farewell_email_task(
    user_id: int,
    email: str,
    full_name: str,
    sub_status: Literal['trial', 'subscription'],
    exp_date: timezone.datetime,
    plan: str,
):
    """Schedules a task to send a farewell email."""
    try:
        client = tasks_v2.CloudTasksClient()
        if settings.STAGE:
            queue = settings.STAGE_QUEUE_FAREWELL_EMAIL
            url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/send_farewell_email/"
        else:
            queue = settings.PROD_QUEUE_FAREWELL_EMAIL
            url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/send_farewell_email/"

        parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)

        payload = {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "sub_status": sub_status,
            "exp_date": exp_date,
            "plan": plan,
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            },
        }

        response = client.create_task(parent=parent, task=task)
        logging.debug(f"Created farewell email task: {response.name} for user {user_id}")

    except Exception as e:
        logging.error(f"Failed to create create_send_farewell_email_task: {str(e)}")
        raise


# 3rd TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def send_farewell_email_task_view(request):
    """Handles the Cloud Task for sending a farewell email."""
    try:
        payload = request.data
        user_id = payload.get("user_id")
        email = payload.get("email")
        full_name = payload.get("full_name")
        sub_status = payload.get("sub_status")
        exp_date = payload.get("exp_date")
        plan = payload.get("plan")

        if not all([user_id, email, full_name, sub_status, exp_date, plan]):
            logging.warning("Missing required fields: user_id, email, full_name, sub_status, exp_date, plan in send_farewell_email_task_view")
            return Response(status=400)

        EventManager().sendEvent(
            "pr_webapp_unsubscribed_email_sent",
            user_id,
            topic="app",
        )
        send_template_email(
            email,
            36175373,
            full_name,
            'farewell',
            status=sub_status,
            date=exp_date,
            plan=plan
        )
        logging.debug(f"Farewell email sent to user {user_id} ({email})")
        return Response(status=200)

    except Exception as e:
        logging.error(f"Error processing send_farewell_email task: {e}")
        return Response(status=500)


# 4th TASK
def create_send_cloud_event_task(
    topic: Literal['app', 'funnel'],
    event_name: str,
    user_id: int | str,
    **kwargs
):
    """Schedules a task to send a cloud event."""
    try:
        client = tasks_v2.CloudTasksClient()
        if settings.STAGE:
            queue = settings.STAGE_QUEUE_CLOUD_EVENT
            url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/send_cloud_event/"
        else:
            queue = settings.PROD_QUEUE_FAREWELL_EMAIL
            url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/send_cloud_event/"

        parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)


        topic_id = settings.PUBSUB_APP_TOPIC_ID if topic == "app" else settings.PUBSUB_FUNNEL_TOPIC_ID

        payload = {
            "topic": topic,
            "topic_id": topic_id,
            "event_name": event_name,
            "user_id": user_id,
            "kwargs": kwargs,
        }

        print(kwargs)

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            },
        }

        response = client.create_task(parent=parent, task=task)
        logging.debug(f"Created create_send_cloud_event_task: {response.name} for event '{event_name}' and user {user_id}")

    except Exception as e:
        logging.error(f"Failed to create create_send_cloud_event_task: {str(e)}")
        raise


# 4th TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def send_cloud_event_task_view(request):
    """Handles the Cloud Task for sending a cloud event."""
    try:
        payload = request.data

        topic = payload.get("topic")
        topic_id = payload.get("topic_id")
        event_name = payload.get("event_name")
        user_id = payload.get("user_id")
        kwargs = payload.get("kwargs", {})

        if not all([topic, topic_id, event_name, user_id]):
            logging.warning("Missing required fields: topic, topic_id, event_name, user_id in send_cloud_event_task_view")
            return Response(status=400)

        user = CustomUser.objects.get(id=user_id)
        fi = user.funnel_info or {}
        geo = fi.get("geolocation", {})
        em = EventManager(user.payment_system)  # type: ignore

        em.sendCloudEvent(
            topic_id,
            event_name,
            user.device_id,
            user.pk,
            ip=fi.pop("ip", None),
            referrer=fi.pop("referer", None),
            language=fi.pop("language", None),
            country_code=geo.get("country_code", None),
            country=geo.get("country_name", None),
            city=geo.get("city", None),
            region=geo.get("region", None),
            **kwargs
        )

        logging.debug(f"Cloud event '{event_name}' sent for user {user_id}")
        return Response(status=200)

    except Exception as e:
        logging.error(f"Error processing send_cloud_event_task_view: {e}")
        return Response(status=500)

# 5th TASK
def create_publish_payment_task(topic_id: str, data: dict):

    client = tasks_v2.CloudTasksClient()
    if settings.STAGE:
        queue = settings.STAGE_QUEUE_PUBLISH_PAYMENT
        url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/publish_payment/"
    else:
        queue = settings.PROD_QUEUE_PUBLISH_PAYMENT
        url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/publish_payment/"

    parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)

    try:
        serializer = PaymentsSerializer(data=data)
        if not serializer.is_valid():
            logging.error("Web analytics: create_publish_payment_task: Invalid data! errors=%s", str(serializer.errors))
            raise ValueError("Invalid data in create_publish_payment_task")

        payload = {
            "topic_id": topic_id,
            "data": serializer.data,
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            },
        }

        client.create_task(parent=parent, task=task)
        logging.debug("Publish payment task created for topic %s", topic_id)
    except Exception as e:
        logging.error(f"Error processing create_publish_payment_task: {str(e)}")
        raise

# 5th TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def publish_payment_task_view(request):
    """Handles the Cloud Task for publishing a payment message."""
    try:
        payload = request.data
        topic_id = payload.get("topic_id")
        data = payload.get("data")

        if not topic_id or not data:
            logging.error("publish_payment_task: Missing topic_id or data")
            return Response(status=400)  # Bad Request

        publishMessage(topic_id, data)
        logging.debug("Payment message published for topic %s", topic_id)
        return Response(status=200)

    except Exception as e:
        logging.debug("publish_payment_task: Error processing task: %s", str(e))
        return Response(status=500)


# 6th TASK
def create_publish_event_task(topic_id: str, data: dict):
    """Schedules a task to publish an event message."""

    client = tasks_v2.CloudTasksClient()
    if settings.STAGE:
        queue = settings.STAGE_QUEUE_PUBLISH_EVENT
        url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/publish_event/"
    else:
        queue = settings.PROD_QUEUE_PUBLISH_EVENT
        url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/publish_event/"

    parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)

    try:
        serializer = EventRawSerializer(data=data)
        if not serializer.is_valid():
            logging.error("Web analytics: create_publish_event_task: Invalid data! errors=%s", str(serializer.errors))
            raise ValueError("Invalid data")

        payload = {
            "topic_id": topic_id,
            "data": serializer.data,
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            },
        }

        client.create_task(parent=parent, task=task)
        logging.debug("Publish payment task created for topic %s", topic_id)
    except Exception as e:
        logging.error(f"Error processing create_publish_event_task: {str(e)}")
        raise

# 6th TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def publish_event_task_view(request):
    """Handles the Cloud Task for publishing an event message."""
    try:
        payload = request.data
        topic_id = payload.get("topic_id")
        data = payload.get("data")

        if not topic_id or not data:
            logging.error("publish_event_task: Missing topic_id or data")
            return Response(status=400)

        publishMessage(topic_id, data)
        logging.debug("Event message published for topic %s", topic_id)
        return Response(status=200)

    except Exception as e:
        logging.error("publish_event_task: Error processing task: %s", str(e))
        return Response(status=500)

# 7th TASK
def create_bind_device_task(device_id: str, user_id: str | int):
    """Schedules a task to bind a device to a user."""

    client = tasks_v2.CloudTasksClient()
    if settings.STAGE:
        queue = settings.STAGE_QUEUE_BIND_DEVICE
        url = f"{settings.STAGE_USERS_SERVICE_URL}/cloud_tasks/bind_device_to_user/"
    else:
        queue = settings.PROD_QUEUE_BIND_DEVICE
        url = f"{settings.PROD_USERS_SERVICE_URL}/cloud_tasks/bind_device_to_user/"

    parent = client.queue_path(settings.GCP_PROJECT_ID, settings.GCP_LOCATION, queue)

    try:
        ts = round(timezone.now().timestamp() * 1e6)
        payload = {
            "device_id": device_id,
            "user_id": str(user_id),
            "received_at": ts,
            "server_processed_at": ts,
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload, cls=DateTimeEncoder).encode()
            },
        }

        client.create_task(parent=parent, task=task)
        logging.debug("Bind device task created for device %s and user %s", device_id, user_id)
    except Exception as e:
        logging.error(f"Error processing create_bind_device_task: {str(e)}")
        raise

# 7th TASK endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def bind_device_to_user_task_view(request):
    """Handles the Cloud Task for binding a device to a user."""
    try:
        payload = request.data
        device_id = payload.get("device_id")
        user_id = payload.get("user_id")
        received_at = payload.get("received_at")
        server_processed_at = payload.get("server_processed_at")

        if not all([device_id, user_id, received_at, server_processed_at]):
            logging.error("bind_device_to_user_task: Missing required fields")
            return Response(status=400)

        publishMessage(settings.PUBSUB_UDID_TOPIC_ID, payload)
        logging.info("Device binding message published for device %s and user %s", device_id, user_id)
        return Response(status=200)

    except Exception as e:
        logging.error("bind_device_to_user_task: Error processing task: %s", str(e))
        return Response(status=500)
    
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------


# 1ST TASK
# @app.task(ignore_result=True)
# def send_welcome(user_id: int, email: str):
#     EventManager().sendEvent("pr_webapp_email_welcome_sent", user_id, topic="app")
#     return send_template_email(
#         email,
#         35698437,
#         None,
#         email_theme='welcome',
#         is_task=True
#     )

# 2nd TASK
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

# 3rd TASK
# @app.task(ignore_result=True)
# def send_farewell_email(user_id: int, email: str, full_name: str, sub_status: Literal['trial', 'subscription'], exp_date: timezone.datetime, plan: str):
#     EventManager().sendEvent(
#         "pr_webapp_unsubscribed_email_sent",
#         user_id,
#         topic="app",
#     )
#     return send_template_email(
#         email,
#         36175373,
#         full_name,
#         'farewell',
#         status=sub_status,
#         date=exp_date,
#         plan=plan
#     )

# 4th TASK
# @app.task  # TODO (DEV-85): causes Segmentation fault when used as a celery task
# def sendCloudEventTask(topic: Literal['app', 'funnel'], event_name: str, user_id: int | str, **kwargs):
#     topic_id = settings.PUBSUB_APP_TOPIC_ID if topic == "app" else settings.PUBSUB_FUNNEL_TOPIC_ID
#     user = CustomUser.objects.get(id=user_id)
#     fi = user.funnel_info or {}
#     geo = fi.get("geolocation", {})
#     em = EventManager(user.payment_system)  # type: ignore
#     return em.sendCloudEvent(
#         topic_id,
#         event_name,
#         user.device_id,
#         user.pk,
#         ip=fi.pop("ip", None),
#         referrer=fi.pop("referer", None),
#         language=fi.pop("language", None),
#         country_code=geo.get("country_code", None),
#         country=geo.get("country_name", None),
#         city=geo.get("city", None),
#         region=geo.get("region", None),
#         **kwargs
#     )


# 5th TASK
# @app.task
# def publishPayment(topic_id: str, data: dict):
#     serializer = PaymentsSerializer(data=data)
#     if not serializer.is_valid():
#         logging.error("Web analytics: publishPayment: Invalid data! errors=%s", str(serializer.errors))
#         return "Invalid data."
#     return publishMessage(topic_id, serializer.data)

# 6th TASK
# @app.task
# def publishEvent(topic_id: str, data: dict):
#     serializer = EventRawSerializer(data=data)
#     if not serializer.is_valid():
#         logging.error("Web analytics: publishEvent: Invalid data! errors=%s", str(serializer.errors))
#         return "Invalid data."
#     return publishMessage(topic_id, serializer.data)


# 7th TASK
# @app.task
# def bindDeviceToUser(device_id: str, user_id: str | int):
#     """Publish message to the GCloud pubsub that pushes messages to BigQuery table on user-device-ids.

#         :param device_id: Device ID
#         :type device_id: str
#         :param user_id: User ID
#         :type user_id: str | int
#     """
#     ts = round(timezone.now().timestamp() * 1e6)
#     data = {
#         "device_id": device_id,
#         "user_id": str(user_id),
#         "received_at": ts,
#         "server_processed_at": ts,
#     }
#     return publishMessage(settings.PUBSUB_UDID_TOPIC_ID, data)

