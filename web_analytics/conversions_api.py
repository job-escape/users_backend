import logging
import time

from django.conf import settings
from facebook_business.adobjects.serverside.action_source import ActionSource
from facebook_business.adobjects.serverside.custom_data import CustomData
from facebook_business.adobjects.serverside.event import Event
from facebook_business.adobjects.serverside.event_request import EventRequest
from facebook_business.adobjects.serverside.user_data import UserData
from facebook_business.api import FacebookAdsApi


def get_ltv(geo, offer, pm):
    logging.debug("get_ltv geo=%s, offer=%s, pm=%s", str(geo), str(offer), str(pm))
    if geo not in settings.T1_COUNTRIES:
        # WW
        if pm in ["apple_pay", "solidgate_applepay"]:
            # ApplePay
            if offer == "1Week":
                return 23.5
            if offer == "12Week":
                return 54.7
            # 4Week
            return 39.6
        # Card
        if offer == "1Week":
            return 20.5
        if offer == "12Week":
            return 47.8
        # 4Week
        return 34.4
    # T1
    if pm in ["apple_pay", "solidgate_applepay"]:
        # ApplePay
        if offer == "1Week":
            return 28.6
        if offer == "12Week":
            return 53.9
        # 4Week
        return 45.9
    # Card
    if offer == "1Week":
        return 28.2
    if offer == "12Week":
        return 45.8
    # 4Week
    return 43.7


class FacebookApi:
    _a: FacebookAdsApi

    def __init__(self) -> None:
        self._a = FacebookAdsApi.init(access_token=settings.CONVERSIONS_SECRET)

    def sendEvent(self, **kwargs):
        logging.debug("ConversionsAPI: sendEvent: %s", str(kwargs))
        data = {
            'email': kwargs['email'],
            # It is recommended to send Client IP and User Agent for Conversions API Events.
            # client_ip_address=kwargs['client_ip_address'],
            # client_user_agent=kwargs['client_user_agent'],
        }
        if kwargs.get("fbc", False):
            data['fbc'] = kwargs['fbc']
        if kwargs.get("fbp", False):
            data['fbp'] = kwargs['fbp']
        user_data = UserData(**data)
        if kwargs.get("currency", None) and kwargs.get("value", None):
            custom_data = CustomData(  # type: ignore
                currency=kwargs['currency'],
                value=kwargs['value'],
            )
        else:
            custom_data = None

        event = Event(
            event_name=kwargs['event_name'],
            event_time=int(time.time()),
            event_id=kwargs['event_id'],
            # event_source_url=kwargs['event_source_url'],
            action_source=ActionSource.WEBSITE,
            # data_processing_options=[],
            # data_processing_options_country=None,
            user_data=user_data,
            custom_data=custom_data,  # type: ignore
        )
        events = [event]
        event_request = EventRequest(
            events=events,
            pixel_id=settings.CONVERSIONS_PIXEL_ID,
            test_event_code=kwargs.get('test_event_code', None)
        )
        return event_request.execute()

    def sendLeadEvent(self, **kwargs):
        kwargs['event_name'] = 'Lead'
        kwargs.setdefault('event_source_url', settings.FRONTEND_FUNNEL_URL+'/chat-v3/plan')
        return self.sendEvent(**kwargs)

    def sendPurchaseEvent(self, **kwargs):
        kwargs['event_name'] = 'Purchase'
        kwargs.setdefault('event_source_url', settings.FRONTEND_FUNNEL_URL+'/chat-v3/selling-page')
        if kwargs.get("currency", None) and kwargs.get("event_id", None):
            kwargs['value'] = get_ltv(kwargs.get("country_code", None), kwargs.pop("offer", None), kwargs.pop("pm", None))
            return self.sendEvent(**kwargs)
        logging.warning("ConversionsAPI: Purchase event was not sent because there is no currency or event_id!")
        return False
