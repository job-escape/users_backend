from django.views.debug import ExceptionReporter
from rest_framework.views import exception_handler


def handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # Now add the HTTP status code to the response.
    if response is not None:
        response.data['status_code'] = response.status_code

    return response


class CustomExceptionReporter(ExceptionReporter):
    """Organize and coordinate reporting on exceptions."""

    # @property
    # def html_template_path(self):
    #     return builtin_template_path("technical_500.html")

    # @property
    # def text_template_path(self):
    #     return builtin_template_path("technical_500.txt")
