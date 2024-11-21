from typing import Any

from amplitude import Amplitude, BaseEvent
from django.conf import settings


class AmplitudeApi:
    _a: Amplitude

    def __init__(self) -> None:
        amplitude = Amplitude(settings.AMPLITUDE_API_KEY)
        amplitude.configuration.min_id_length = 1
        self._a = amplitude

    def trackBaseEvent(self, event_type: str, user_id: str, event_properties: dict[str, Any] | None = None):
        self._a.track(
            BaseEvent(
                event_type=event_type,
                user_id=f"amp_user_{user_id}",
                event_properties=event_properties,
            )
        )

    def trackPurchaseFail(self, user_id: str, detail: dict, message: str | None = None):
        self.trackBaseEvent("pr_funnel_subscribe_failed", user_id, {"detail": detail, "message": message})
