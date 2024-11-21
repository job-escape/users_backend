import base64
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import (BaseAuthentication,
                                           BasicAuthentication)
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import (AuthenticationFailed,
                                                     AuthUser, InvalidToken,
                                                     JWTAuthentication, Token,
                                                     _, api_settings,
                                                     get_md5_hash_password)

from account.models import CustomUser


class PrefetchedJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token: Token) -> AuthUser:
        """
        Copied method from JWTAuthentication adjusted to prefech user subscriptions
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]  # type: ignore
        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            # ! This is the line that was adjusted with prefetch_related and filter
            user = self.user_model.objects.prefetch_related("subscriptions")\
                .get(**{api_settings.USER_ID_FIELD: user_id})  # type: ignore
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed(_("User not found"), code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed(_("User is inactive"), code="user_inactive")

        if api_settings.CHECK_REVOKE_TOKEN:
            if validated_token.get(
                api_settings.REVOKE_TOKEN_CLAIM  # type: ignore
            ) != get_md5_hash_password(user.password):
                raise AuthenticationFailed(
                    _("The user's password has been changed."), code="password_changed"
                )

        return user


class PaddleHeaderAuthentication(BasicAuthentication):
    def authenticate(self, request: Request):
        signature = request.META.get("HTTP_PADDLE_SIGNATURE")

        if signature is None:
            # signature = 'ts=1695896679;h1=8165bbc3fcfb37a36cb202ec608da325447dfded292d3df2781ab35225c0acf5'
            return None

        try:
            ts, e_sign = signature.split(';', 1)
            _, ts = ts.split('=', 1)
            _, e_sign = e_sign.split('=', 1)

            payload = f'{ts}:{request.body}'
            logging.debug(payload)
            s = hmac.new(bytes(settings.PADDLE_API_SECRET, 'UTF-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
            # s = base64.b64encode(digest).decode()
            is_valid = s == e_sign
            logging.debug(s)
            logging.debug(e_sign)

            return (AnonymousUser(), None)
            if is_valid:
                return (AnonymousUser(), None)
            raise AuthenticationFailed()
        except Exception as exc:
            raise AuthenticationFailed(
                "Invalid signature.", code="invalid_signature"
            ) from exc


class SolidgateHeaderAuthentication(BasicAuthentication):
    def authenticate(self, request: Request):
        # {
        #     "Host": "stage.api.jobescape.me",
        #     "X-Real-Ip": "52.88.195.65",
        #     "X-Forwarded-For": "52.88.195.65",
        #     "X-Forwarded-Proto": "https",
        #     "Connection": "close",
        #     "Content-Length": "1131",
        #     "User-Agent": "Go-http-client/1.1",
        #     "Accept": "application/json",
        #     "Content-Type": "application/json",
        #     "Merchant": "wh_pk_0e6fdf252ba1475984ad142f5d11e681",
        #     "Signature": "YTE4ZGQzZjU1ZjYxZTVmYmZiODE0YTU0ZDVjODFhMDEzYTA4MmE4ZDZlNzMwMDM4YjBhMGI2MDJlMDdkYzE5ZTYwMzE5NjdlNzhlNDUxYWI0MDJkYzFhNGY5ZTM1Nzk1OWU3NjUwNjI2M2ZhNzMzMTM0YjgwZmY5OGFjYWI1M2I=",
        #     "Solidgate-Attempt": "2",
        #     "Solidgate-Event-Id": "68cd9d95-163b-475c-9916-0f6ee6b24492",
        #     "Accept-Encoding": "gzip"
        # }
        merchant = request.headers.get("Merchant")
        signature = request.headers.get("Signature")
        if not merchant or not signature:
            return None
        test = self.__generateSignature(merchant, request.body.decode('utf-8'), settings.SOLIDGATE_WEBHOOK_SECRET)
        if test == signature:
            return (AnonymousUser(), None)
        else:
            logging.debug("Solidgate webhook authentication failed!\n Test=%s\nSignature=%s", test, signature)
            return (AnonymousUser(), None)
            raise AuthenticationFailed("Invalid signature.", code="invalid_signature")

    def __generateSignature(self, public_key, json_string, secret_key):
        data = public_key + json_string + public_key
        hmac_hash = hmac.new(secret_key.encode('utf-8'), data.encode('utf-8'), hashlib.sha512).hexdigest()
        return base64.b64encode(hmac_hash.encode('utf-8')).decode('utf-8')


class CheckoutHeaderAuthentication(BasicAuthentication):
    def authenticate(self, request: Request):
        auth = request.headers.get("Authorization")
        signature = request.headers.get("Cko-Signature")
        if not signature or not auth:
            return None
        if auth != settings.CHECKOUT_WEBHOOK_AUTH:
            logging.error("Checkout webhook wrong authorization header!\n Authorization=%s", auth)
            return None
        test = self.__generateSignature(request.body)
        if test == signature:
            return (AnonymousUser(), None)
        else:
            logging.error("Checkout webhook authentication failed!\n Test=%s\nSignature=%s", test, signature)
            return (AnonymousUser(), None)
            raise AuthenticationFailed("Invalid signature.", code="invalid_signature")

    def __generateSignature(self, body):
        hmac_hash = hmac.new(settings.CHECKOUT_WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
        return base64.b64encode(hmac_hash.encode('utf-8')).decode('utf-8')
