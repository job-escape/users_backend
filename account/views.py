import json
import random
import string
from typing import Any
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.db.transaction import atomic
from django.utils import timezone
from django.utils.datetime_safe import datetime
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import CustomUser, UserOnboarding
from account.serializers import (UserAddNameSerializer, UserBasicSerializer,
                                 UserFunnelSerializer,
                                 UserOnboardingSerializer,
                                 UserRegisterSerializer,
                                 UserResetPasswordSerializer, UserSerializer,
                                 UserSetPasswordSerializer,
                                 UserStreakCreateSerializer,
                                 UserStreakParamsSerializer,
                                 UserStreakSerializer,
                                 UserUpdateNotificationSerializer,
                                 UserUpdatePasswordSerializer,
                                 UserVerifyCodeRequestSerializer,
                                 UserVerifyCodeResponseSerializer,
                                 UserVideoCreditSerializer,
                                 )
from account.utils import get_user_or_404, select_payment_system, fetch_progress_counts_from_microservices
from custom.custom_exceptions import BadRequest
from custom.custom_permissions import IsSelf
# from interview_prep.models import UserInterviewPrep
# from jlab.models import Project, ProjectTask
# from progress_v2.models import CourseProgress, LearningPathProgress
from shared.emailer import (add_to_addressbook, send_password_code,
                            send_welcome, update_addressbook)
from subscription.gateway import PaymentGateway
from user_goal.models import UserDailyGoal
from web_analytics.event_manager import EventManager
# from personal_plan.models import PersonalPlan
# from web_analytics.tasks import bindDeviceToUser

from google_tasks.tasks import (
    create_send_welcome_task,
    create_bind_device_task,
)

DEFAULT_COUNTRY_CODE = 'NN'


class UnregisteredUserViewSet(viewsets.GenericViewSet):
    """
        Viewset for creating a user, getting/updating a user that has not yet registered, and registering such a user.
    """
    queryset = CustomUser.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'register':
            return UserRegisterSerializer
        if self.action == 'get_or_create':
            return UserFunnelSerializer
        if self.action == 'add_name':
            return UserAddNameSerializer
        return None

    @action(methods=['post'], detail=True)
    def register(self, request, *args, **kwargs):
        """
            Set password for a new user, send events and welcome email.
            Returns user data and access and refresh tokens.
        """
        user: CustomUser = self.get_object()
        email = user.email
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # TODO (DEV-109): add request rate limiting to this endpoint
        device_id = serializer.validated_data.get("device_id", None)
        if device_id is not None:
            if device_id != user.device_id:
                # bindDeviceToUser.delay(device_id, user.pk)
                create_bind_device_task(device_id, user.pk)
            else:
                serializer.validated_data.pop("device_id")
        password = serializer.validated_data['password']
        password = make_password(password)
        user = serializer.save(password=password, token_set_time=None, payment_email=email)
        data = serializer.data
        refresh = RefreshToken.for_user(user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)  # type: ignore

        # send_welcome.delay(user.pk, user.email)
        create_send_welcome_task(user.pk, user.email)
        # Send webapp event
        EVENT_MANAGER = EventManager(user.payment_system)
        today = timezone.datetime.today()
        event_properties = {
            "webapp_cohort_day": today.day,
            "webapp_cohort_week": today.isocalendar()[1],
            "webapp_cohort_month": today.month,
            "webapp_cohort_year": today.year,
        }
        EVENT_MANAGER.sendEvent("pr_webapp_launch_first_time", user.pk, event_properties, topic="app")
        return Response(data)

    @extend_schema(responses={200: UserBasicSerializer, 201: UserBasicSerializer})
    @action(detail=False, methods=['post'], url_name='get_or_create')
    def get_or_create(self, request):
        """
            Get or create a user with the given email and update data.
            Also calls `bindDeviceToUser`.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.data['email']
        funnel_info = serializer.data['funnel_info']
        country_code = serializer.data.get('country_code', DEFAULT_COUNTRY_CODE)
        email_consent = serializer.data['email_consent']
        payment_system = select_payment_system(email, country_code)
        # Patch-fix randomly occuring Postgres error
        if funnel_info:
            funnel_info = json.loads(json.dumps(funnel_info).replace('\\u0000', ''))
        # Set default data for user instance
        defaults = {"funnel_info": funnel_info} if funnel_info else {}
        if country_code:
            defaults['country_code'] = country_code
        if email_consent:
            defaults['email_consent'] = email_consent
        # Retrieve instance
        if defaults:
            instance, created = CustomUser.objects.update_or_create(defaults=defaults, email=email)
        else:
            instance, created = CustomUser.objects.get_or_create(defaults=defaults, email=email)
        # Track if device ID should be updated and sent to BigQuery
        device_id_updated = True
        # Select payment system, add to email cascade, and send personal plan to new users
        if created:
            instance.device_id = serializer.data.get("device_id", "Unknown")
            instance.payment_system = payment_system
            instance.save()
            if instance.email_consent:
                # Lead email cascade
                add_to_addressbook(email, funnel_info)
            # if instance.funnel_info:
            #     delay = timezone.timedelta(minutes=5)
            #     send_personal_plan.apply_async(
            #         args=[instance.pk, email],
            #         eta=timezone.now() + delay
            #     )
        else:
            if instance.device_id != serializer.data.get("device_id", "Unknown"):
                instance.device_id = serializer.data.get("device_id", "Unknown")
                instance.save()
            else:
                device_id_updated = False
        if device_id_updated:
            create_bind_device_task(instance.device_id, instance.pk)
            # bindDeviceToUser.delay(instance.device_id, instance.pk)

        data: dict = UserBasicSerializer(instance).data  # type: ignore
        data['is_registered'] = bool(instance.password)
        _status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(data, _status)

    @action(detail=False, methods=['post'], url_name='add_name')
    def add_name(self, request):
        """Add User to an addressbook on submitting name (funnel)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.data['email']
        name = serializer.data['name']
        user, created = CustomUser.objects.get_or_create({"full_name": name}, email=email)
        if user.email_consent:
            update_addressbook(email, {"name": name})
        if not created and not user.full_name:
            user.full_name = name
            user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    


class UserViewSet(viewsets.GenericViewSet, mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    """
        Viewset for different operations on registered users.
    """
    queryset = CustomUser.objects.exclude(password='')
    permission_classes = [IsSelf]

    def get_serializer_class(self):
        if self.action == 'set_password':
            return UserSetPasswordSerializer
        if self.action == 'reset_password':
            return UserResetPasswordSerializer
        if self.action == 'verify_code':
            return UserVerifyCodeRequestSerializer
        if self.action == 'update_password':
            return UserUpdatePasswordSerializer
        if self.action == 'job_notification':
            return UserUpdateNotificationSerializer
        if self.action == 'streak':
            return UserStreakSerializer
        if self.action == 'streak_create':
            return UserStreakCreateSerializer
        if self.action in ['video_credit', 'internal_video_credits']:
            return UserVideoCreditSerializer
        if self.action in ['onboarding', 'onboarding_update']:
            return UserOnboardingSerializer
        return UserSerializer

    @atomic
    def perform_destroy(self, instance: CustomUser):
        instance.is_active = False
        instance.save()
        # TODO (DEV-115): nullify other fields and remove related models
        PaymentGateway(instance).cancel_membership()

    @action(detail=False, methods=['get'])
    def profile(self, request: Request):
        """Get user profile information."""
        user = request.user
        data = self.get_serializer(user).data
        return Response(data)

    @action(detail=True, methods=['post'])
    def update_password(self, request: Request, pk=None):
        """
            Update password for a logged-in user if submitted old password is correct.
            Returns user email.
        """
        user = request.user
        ser = self.get_serializer(user, data=request.data)
        ser.is_valid(raise_exception=True)
        password = ser.validated_data['password']
        password = make_password(password)
        ser.save(password=password)
        return Response(ser.data)

    @extend_schema(responses={204: None})
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def set_password(self, request: Request):
        """
            Update user password if submitted PR code is correct.
            `email` is a required field only for unathenticated users.
        """
        # TODO (DEV-109): add request rate limiting to this endpoint
        user = get_user_or_404(request, self.get_queryset())
        request.data.pop("email", None)  # type: ignore
        ser = self.get_serializer(user, data=request.data)
        ser.is_valid(raise_exception=True)
        password = ser.validated_data.get("password")
        password = make_password(password)
        ser.save(password=password, code=None, code_set_time=None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={204: None})
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def reset_password(self, request: Request):
        """
            Generates and sets password reset code. Sends an email with the code.
            `email` is a required field only for unathenticated users.
        """
        # TODO (DEV-109): add request rate limiting to this endpoint
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = get_user_or_404(request, self.get_queryset())
        # TODO (DEV-110): encapsulate code generation algorithm within User.objects.Manager
        code = ''.join(random.choices(string.digits, k=6))
        user.code = code
        user.code_set_time = timezone.now()
        user.save()
        send_password_code(user.pk, user.full_name, user.email, code)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: UserVerifyCodeResponseSerializer})
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verify_code(self, request: Request, pk=None):
        """
            Verify that the password reset (PR) code is equal to the user's PR code.
            Returns 400 if user does not have any code.
            `email` is a required field only for unathenticated users.
        """
        # TODO (DEV-109): add request rate limiting to this endpoint
        user = get_user_or_404(request, self.get_queryset())
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = ser.data["code"]
        if not user.code:
            raise BadRequest("User is not allowed to verify.")
        return Response({"valid": user.code == code})

    @extend_schema(parameters=[UserStreakParamsSerializer])
    @action(detail=False)
    def streak(self, request: Request):
        """
            Return streak information for the next week starting from the `start`
            along with additional statistical information.
        """
        ser = UserStreakParamsSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data: Any = ser.data
        user = request.user
        start = datetime.strptime(data['start'], "%Y-%m-%d")
        end = start + timezone.timedelta(days=6)
        dates = UserDailyGoal.objects.filter(
            user=user,
            date__range=[start, end]
        ).values_list("date", flat=True)
        streak = [False] * 7
        for day in range(7):
            date = start + timezone.timedelta(days=day)
            if date.date() in dates:
                streak[day] = True
        
        academy_progress_data = fetch_progress_counts_from_microservices(settings.ACADEMY_SERVICE_URL, auth_token=request.auth)
        ai_progress_data = fetch_progress_counts_from_microservices(settings.AI_SERVICE_URL, auth_token=request.auth)
        response_data = {
            "courses": academy_progress_data.get("elements", 0),
            "modules": academy_progress_data.get("modules", 0),
            'chats': ai_progress_data.get('chats', 0),
            "interviews": ai_progress_data.get("interviews", 0),
            "streak": streak
        }
        ser = self.get_serializer(data=response_data)
        ser.is_valid()
        return Response(ser.data)

    @extend_schema(responses={201: None})
    @streak.mapping.post
    def streak_create(self, request: Request):
        """Create UserDailyGoal for the user for the provided day as completed if not exists already."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            if UserDailyGoal.objects.filter(user=request.user, date=ser.data['date']).exists():
                return Response(status=status.HTTP_204_NO_CONTENT)
            UserDailyGoal.objects.create(user=request.user, date=ser.data['date'], completed=True)
        except:
            raise BadRequest("Invalid date.")
        return Response(status=status.HTTP_201_CREATED)

    @action(detail=False)
    def video_credit(self, request: Request):
        """Update (renew) User's video credits if previous credits were expired."""
        user: CustomUser = request.user
        if user.video_credit_due <= timezone.now():
            user.video_credit_due = timezone.now() + timezone.timedelta(days=30)
            user.video_credit = 10
            user.save()
        ser = self.get_serializer(user)
        return Response(ser.data)
    
    @action(detail=False, methods=['get', 'patch'])
    def internal_video_credits(self, request):
        user: CustomUser = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        if request.method == 'PATCH':
            video_credit = request.data.get('video_credit', None)
            if video_credit is not None:
                user.video_credit = video_credit
                user.save()
                return Response({'message': 'Video credit updated successfully.'}, status=status.HTTP_200_OK)
            return Response({'error': 'No video credit provided.'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=None, responses={200: UserOnboardingSerializer, 201: UserOnboardingSerializer})
    @action(['post'], False)
    def onboarding(self, request: Request):
        """Retrieve (and/or create) UserOnboarding with onboarding information."""
        user = request.user
        instance, created = UserOnboarding.objects.get_or_create(user=user)
        status_ = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        ser = self.get_serializer(instance)
        return Response(ser.data, status_)

    @extend_schema(request=UserOnboardingSerializer)
    @onboarding.mapping.patch
    def onboarding_update(self, request: Request):
        """Update (and/or create) UserOnboarding."""
        user = request.user
        instance, _ = UserOnboarding.objects.get_or_create(user=user)
        ser = self.get_serializer(instance, request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
