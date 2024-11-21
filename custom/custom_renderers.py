import json

from rest_framework.renderers import BaseRenderer
from rest_framework_xml.renderers import XMLRenderer


class ServerSentEventRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'txt'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, dict):
            data = json.dumps(data)
        return data


class CustomXMLRenderer(XMLRenderer):
    media_type = "text/xml"
    root_tag_name = "Response"
