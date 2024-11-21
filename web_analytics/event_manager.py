import logging
import uuid
from typing import Any, Literal

import posthog
from django.conf import settings
from django.utils import timezone
from pandas import Period

from account.models import CustomUser, GatewayChoices
from web_analytics.amplitude import AmplitudeApi
from web_analytics.conversions_api import FacebookApi
from web_analytics.tasks import publishEvent


class EventManager():
    a: AmplitudeApi
    f: FacebookApi
    p = posthog
    payment_system: GatewayChoices | None

    def __init__(self, payment_system: GatewayChoices | None = None) -> None:
        self.a = AmplitudeApi()
        self.f = FacebookApi()
        self.payment_system = payment_system

    def sendPurchaseEvent(self, user_id: int | str, device_id: str, email: str,  subscription_name: str, funnel_info: dict | None, props: dict | None = None):
        if props is None:
            props = {}
        props.update({
            "subscription": subscription_name,
            # "pricing_id": subscription.
            # "pricing_name".
            "cohort_year": timezone.datetime.now().year,
            "cohort_week": timezone.datetime.today().isocalendar()[1],
            "cohort_day": Period(timezone.datetime.today(), freq='D').day_of_year,
        })
        fbc = None
        fbp = None
        if funnel_info:
            props.update({
                "email": funnel_info.get("email", ""),
                "gender": funnel_info.get("gender", {}).get("value", "") if isinstance(funnel_info.get("gender"), dict) else "",
                "age": funnel_info.get("age", {}).get("value", "") if isinstance(funnel_info.get("age"), dict) else "",
                "goal": funnel_info.get("goal", {}).get("value", "") if isinstance(funnel_info.get("goal"), dict) else "",
                "utm_ad": funnel_info.get("utm_ad", ""),
                "utm_adset": funnel_info.get("utm_adset", ""),
                "utm_source": funnel_info.get("utm_source", ""),
                "country_code": funnel_info.get("country_code", ""),
                "country_name": funnel_info.get("country_name", ""),
                "utm_campaign": funnel_info.get("utm_campaign", ""),
                "email_consent": funnel_info.get("email_consent", ""),
                "utm_placement": funnel_info.get("utm_placement", ""),
                "utm_keyword": funnel_info.get("utm_keyword", ""),
                "utm_adgroupid": funnel_info.get("utm_adgroupid", ""),
                "ip": funnel_info.get("ip", ""),
            })
            fbp = funnel_info.get("fbp", None)
            fbc = funnel_info.get("fbc", None)
        else:
            logging.warning("Received empty funnel_info for user_id=%d!", user_id)

        fb_event_id = str(uuid.uuid4())
        self.f.sendPurchaseEvent(
            email=props.get("email") or email,
            currency=props.get("currency", None),
            country_code=props.get("country_code", None),
            fbc=fbc,
            fbp=fbp,
            event_id=fb_event_id,
            offer=subscription_name,
            pm=props.get("payment_method", None),
        )
        self.sendEvent("pr_funnel_subscribe", user_id, props, topic="funnel")

        # if self.payment_system:
        #     props["payment_method"] = self.payment_system
        # sendCloudEventTask.delay("funnel", "pr_funnel_subscribe", user_id, event_metadata=props)

        # with open(settings.BASE_DIR.joinpath('files/last_purchase_date.txt'), "w+", encoding=encoding.DEFAULT_LOCALE_ENCODING) as f:
        #     f.write(timezone.now().isoformat())
        return fb_event_id
    
    def sendEvent(self, event_name: str, user_id: int | str, props: dict[str, Any] | None = None, amplitude: bool = True, pubsub: bool = True, topic: Literal['app', 'funnel'] = "app"):
        """Send an event to Amplitude and Posthog

        :param event_name: Event name
        :type event_name: str
        :param user_id: User id that is used as event id
        :type user_id: int | str
        :param props: Other event properties, defaults to None
        :type props: dict | None, optional
        :param amplitude: send events to Amplitude if true, defaults to True
        :type amplitude: bool, optional
        """
        if pubsub:
            from google_tasks.tasks import create_send_cloud_event_task
            create_send_cloud_event_task(topic, event_name, user_id, event_metadata=props)
        if props is None:
            props = {}
        uid = str(user_id)
        if self.payment_system:
            props["payment_method"] = self.payment_system

        self.p.capture(uid, event_name, props)
        if amplitude:
            props.pop("$set_once", None)
            self.a.trackBaseEvent(event_name, uid, props)

    def sendPurchaseFailedEvent(self, user_id: int | str, detail: dict | int | str | None = None, message: str = ""):
        props: dict[str, Any] = {
            "message": message,
        }
        if detail is not None:
            props["detail"] = detail
        self.sendEvent("pr_funnel_subscribe_failed", user_id, props, topic="funnel")

    def sendCloudEvent(
            self,
            topic_id: str,
            event_name: str,
            device_id: str,
            user_id: str | int | None = None,
            path: str = "",
            **kwargs
    ):
        """Send event to Google Cloud infrastructure through a task.

        :param topic_id: Google Cloud PubSub topic ID (use settings variables)
        :type topic_id: str
        :param event_name: Event name
        :type event_name: str
        :param device_id: Device ID
        :type device_id: str
        :param path: Event cause path
        :type path: str
        :param user_id: User ID, defaults to None
        :type user_id: str | int | None, optional
        :param **kwargs: See "Additional parameters"


        ### Additional parameters

        :param ip: Client IP address
        :type ip: str | None, optional
        :param user_agent: 
        :type user_agent: str | None, optional
        :param referrer: 
        :type referrer: str | None, optional
        :param language: 
        :type language: str | None, optional
        :param country_code: 
        :type country_code: str | None, optional
        :param country: 
        :type country: str | None, optional
        :param city: 
        :type city: str | None, optional
        :param region: 
        :type region: str | None, optional
        :param attribution_id: 
        :type attribution_id: str | None, optional
        :param event_metadata: 
        :type event_metadata: dict | None, optional
        :param user_metadata: 
        :type user_metadata: dict | None, optional
        :param query_parameters: 
        :type query_parameters: dict | None, optional
        """
        data = {
            "event_id": uuid.uuid4(),
            "event_name": event_name,
            "user_id": user_id,
            "device_id": device_id,
            "path": path,
            "timestamp": round(timezone.now().timestamp() * 1e6),
        }
        data.update(kwargs)
        publishEvent(topic_id, data)


# @app.task  # TODO (DEV-85): causes Segmentation fault when used as a celery task
def sendCloudEventTask(topic: Literal['app', 'funnel'], event_name: str, user_id: int | str, **kwargs):
    topic_id = settings.PUBSUB_APP_TOPIC_ID if topic == "app" else settings.PUBSUB_FUNNEL_TOPIC_ID
    user = CustomUser.objects.get(id=user_id)
    fi = user.funnel_info or {}
    geo = fi.get("geolocation", {})
    em = EventManager(user.payment_system)  # type: ignore
    return em.sendCloudEvent(
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
