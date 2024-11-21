from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from account.models import CustomUser, UserOnboarding
from custom import custom_serializer_fields


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'image',
                  'job_notification', 'trustpilot_review', 'personal_plan_pk', 'prompt_upsell', 
                  'mentor_upsell', 'd2_csat', 'd3_csat', 'ai_csat', 'ab_test_48', 'ab_test_51']


class UserUpdateNotificationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField()

    class Meta:
        model = CustomUser
        fields = ['job_notification', "job_title"]


class UserUpdatePasswordSerializer(serializers.ModelSerializer):  # TODO: Check if password validators work
    old_password = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'old_password', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_old_password(self, value):
        assert self.instance, "Instance is not provided"
        user: CustomUser = self.instance
        if user.check_password(value):
            return value
        raise serializers.ValidationError("Wrong password")


class UserSetPasswordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'code', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': False},
        }

    def validate_code(self, value):
        assert self.instance, "Instance is not provided"
        user: CustomUser = self.instance
        if not user.code or value != user.code:
            raise serializers.ValidationError("Invalid code or password reset is not allowed")
        if not user.code_set_time or timezone.now() - user.code_set_time > settings.PASSWORD_TOKEN_EXPIRATION_DELTA:
            raise serializers.ValidationError("Password reset code has expired")
        return value


class UserBasicSerializer(serializers.ModelSerializer):
    is_registered = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'payment_system', 'funnel_info', 'country_code', 'is_registered', 'full_name']


class UserResetPasswordSerializer(serializers.Serializer):
    email = custom_serializer_fields.EmailField(required=False)


class UserAddNameSerializer(serializers.Serializer):
    email = custom_serializer_fields.EmailField()
    name = serializers.CharField()

class UserPersonalPlanSerializer(serializers.Serializer):
    email = custom_serializer_fields.EmailField()
    personal_plan = serializers.IntegerField()


class UserFunnelSerializer(serializers.ModelSerializer):
    email = custom_serializer_fields.EmailField()
    country_code = serializers.CharField(max_length=2, required=False)

    class Meta:
        model = CustomUser
        fields = ['email', 'funnel_info', 'country_code', 'email_consent', 'device_id']


class UserRegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'password', 'confirm_password', 'first_name', 'last_name', 'full_name', 'token', 'access', 'refresh', 'device_id']
        extra_kwargs = {
            'password': {'write_only': True},
            'confirm_password': {'write_only': True},
            'token': {'write_only': True},
            'device_id': {'required': False},
        }

    def validate_token(self, value):
        assert self.instance, "Instance is not provided"
        user: CustomUser = self.instance
        if not user.token or value != user.token:
            raise serializers.ValidationError("Invalid token or registration is not allowed")
        if not user.token_set_time or timezone.now() - user.token_set_time > settings.REGISTRATION_TOKEN_EXPIRATION_DELTA:
            # TODO (DEV-112): Send email with new registration token
            raise serializers.ValidationError("Registration token has expired")
        return None

    def validate(self, attrs):
        if attrs['confirm_password'] != attrs['password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs


class UserVerifyCodeRequestSerializer(serializers.Serializer):
    email = custom_serializer_fields.EmailField(required=False)
    code = serializers.CharField(default="000000")

    def validate_code(self, code):
        try:
            int(code)
            assert len(code) == 6, 'Invalid length (should be 6).'
        except AssertionError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        except ValueError as exc:
            raise serializers.ValidationError('Code should consist of integers.') from exc
        return code


class UserVerifyCodeResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()


class UserStreakParamsSerializer(serializers.Serializer):
    start = serializers.DateField("%Y-%m-%d")  # type: ignore


class UserStreakCreateSerializer(serializers.Serializer):
    date = serializers.DateField("%Y-%m-%d")  # type: ignore


class UserStreakSerializer(serializers.Serializer):
    courses_completed = serializers.IntegerField()
    learning_paths = serializers.IntegerField()
    projects = serializers.IntegerField()
    interviews = serializers.IntegerField()
    streak = serializers.ListField(child=serializers.BooleanField())


class UserVideoCreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["video_credit", "video_credit_due"]


class UserOnboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserOnboarding
        exclude = ["user"]
