"""
URL configuration for jobescape project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path
from drf_spectacular import views as SchemaViews
from rest_framework import routers
from rest_framework_simplejwt import views as JwtViews

from account.views import UnregisteredUserViewSet, UserViewSet
# from ai.views import AiViewSet, ChatViewSet
from custom.custom_viewsets import CustomTokenObtainPairView
from faq.views import ContactFormViewSet, FaqViewSet
from job.views import JobUserViewSet, JobViewSet
from payment_checkout.views import CheckoutViewSet, CheckoutWebhookViewSet
# from payment_paddle import views as PaddleViews
# from payment_paypal.views import PayPalViewSet
# from payment_paytabs.views import PaytabsViewSet
from payment_solidgate.views import SolidgateViewSet, SolidgateWebhookViewSet
# from progress.views import CourseProgressViewSet
from seo_blog.views import BlogCategoryViewSet, BlogViewSet
from subscription.views import (SubscriptionFeedbackViewSet,
                                SubscriptionViewSet, UserSubscriptionViewSet,
                                UpsellViewSet)
from web_analytics.views import HealthcheckViewSet
from webinars.views import WebinarViewSet

from google_tasks.tasks import (
    bind_device_to_user_task_view,
    send_cloud_event_task_view,
    delay_registration_email_view,
    send_farewell_email_task_view,
    publish_event_task_view,
    publish_payment_task_view,
    send_welcome_task_view,
)
from google_tasks.cron_job import (
    charge_users_scheduler_view
)

urlpatterns = [
    # TINYMCE
    path('tinymce/', include('tinymce.urls')),

    # ADMIN
    path('admin/', admin.site.urls),

    # JWT TOKEN
    path('token/', CustomTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
    path('token/refresh/', JwtViews.TokenRefreshView.as_view(),
         name='token_refresh'),
    # path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # SCHEMA
    # download schema
    path('schema/', SchemaViews.SpectacularAPIView.as_view(), name='schema'),
    # schema with swagger UI
    path('schema/swagger-ui/',
         SchemaViews.SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # schema with redoc UI
    path('schema/redoc/',
         SchemaViews.SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

urlpatterns += [
    path('google_tasks/bind_device_to_user/', bind_device_to_user_task_view, name='google_tasks_bind_device_to_user'),
    path('google_tasks/send_cloud_event/', send_cloud_event_task_view, name='google_tasks_send_cloud_event'),
    path('google_tasks/delay_registration_email/', delay_registration_email_view, name='google_tasks_delay_registration_email'),
    path('google_tasks/send_farewell_email/', send_farewell_email_task_view, name='google_tasks_send_farewell_email'),
    path('google_tasks/publish_event/', publish_event_task_view, name='google_tasks_publish_event'),
    path('google_tasks/publish_payment/', publish_payment_task_view, name='google_tasks_publish_payment'),
    path('google_tasks/send_welcome/', send_welcome_task_view, name='google_tasks_send_welcome'),

    path('google_crons/run_charge_users/', charge_users_scheduler_view, name='charge_users_scheduler')
]

if settings.DEBUG:
    # DJANGO-SILK
    urlpatterns.append(path('silk/', include('silk.urls', namespace='silk')))

router = routers.SimpleRouter()
# Healthcheck
router.register(r'healthcheck', HealthcheckViewSet, 'healthcheck')
# Unregistered User API
router.register(r'new_users', UnregisteredUserViewSet)
# Account API
router.register(r'users', UserViewSet)
# Subscription API
router.register(r'subscriptions', SubscriptionViewSet, 'subscriptions')
# User Subscription API
router.register(r'user_subscriptions', UserSubscriptionViewSet, 'user_subscriptions')
# Upsell API
router.register(r'upsell', UpsellViewSet, 'upsell')
# Subscription Feedback API
router.register(r'feedbacks', SubscriptionFeedbackViewSet, 'feedbacks')
# Payment system: Solidgate
router.register(r'webhooks/solidgate', SolidgateWebhookViewSet, 'webhooks')
router.register(r'solidgate', SolidgateViewSet, 'solidgate')
# Payment system: Checkout
router.register(r'webhooks/checkout', CheckoutWebhookViewSet, 'webhooks')
router.register(r'checkout', CheckoutViewSet, 'checkout')
# Profile: FAQ
router.register(r'faq', FaqViewSet, 'faq')
# Profile: ContactForm
router.register(r'contact', ContactFormViewSet, 'contact')
# Landing pages: Blog
router.register(r'blog/category', BlogCategoryViewSet, 'blog/category')
router.register(r'blog', BlogViewSet, 'blog')
# Homepage API
router.register(r'webinars', WebinarViewSet, 'webinars')
# router.register(r'homepage/progress', CourseProgressViewSet, "homepage/progress")
# Jobs API
router.register(r'job', JobViewSet, 'job')
router.register(r'job_user', JobUserViewSet, 'job_user')



# if settings.DEBUG:
#     router.register(r'dump', DumpViewSet, 'dump')

urlpatterns += router.urls
