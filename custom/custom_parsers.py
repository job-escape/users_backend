from rest_framework_xml.parsers import XMLParser


class CustomXMLParser(XMLParser):
    media_type = "text/xml"
