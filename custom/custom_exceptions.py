from rest_framework.exceptions import APIException


class InternalServerError(APIException):
    status_code = 500
    default_detail = 'Internal server error'
    default_code = 'internal_server_error'


class BadRequest(APIException):
    status_code = 400
    default_detail = 'Bad request'
    default_code = 'bad_request'


class Fraud3dsException(Exception):
    pass


class FraudRejectException(Exception):
    pass
