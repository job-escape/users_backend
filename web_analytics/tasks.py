import json
import logging

from django.conf import settings
from django.utils import timezone
from google.cloud.pubsub import PublisherClient

from web_analytics.pubsub import EventRawSerializer, PaymentsSerializer


def publishMessage(topic_id: str, data):
    client = PublisherClient()
    topic_path = client.topic_path(settings.PUBSUB_PROJECT_ID, topic_id)
    b_data = json.dumps(data).encode("utf-8")
    future = client.publish(topic_path, b_data)
    return future.result()


# @app.task
def publishPayment(topic_id: str, data: dict):
    serializer = PaymentsSerializer(data=data)
    if not serializer.is_valid():
        logging.error("Web analytics: publishPayment: Invalid data! errors=%s", str(serializer.errors))
        return "Invalid data."
    return publishMessage(topic_id, serializer.data)


# @app.task
def publishEvent(topic_id: str, data: dict):
    serializer = EventRawSerializer(data=data)
    if not serializer.is_valid():
        logging.error("Web analytics: publishEvent: Invalid data! errors=%s", str(serializer.errors))
        return "Invalid data."
    return publishMessage(topic_id, serializer.data)


# @app.task
def bindDeviceToUser(device_id: str, user_id: str | int):
    """Publish message to the GCloud pubsub that pushes messages to BigQuery table on user-device-ids.

        :param device_id: Device ID
        :type device_id: str
        :param user_id: User ID
        :type user_id: str | int
    """
    ts = round(timezone.now().timestamp() * 1e6)
    data = {
        "device_id": device_id,
        "user_id": str(user_id),
        "received_at": ts,
        "server_processed_at": ts,
    }
    return publishMessage(settings.PUBSUB_UDID_TOPIC_ID, data)
