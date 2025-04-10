from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    create_payment_intent,
    create_monthly_subscription,
    webhook_handler,
    cancel_subscription,
    PaymentViewSet
)

router = DefaultRouter()
router.register(r'payments', PaymentViewSet)

urlpatterns = [
    path('create_payment_intent/', create_payment_intent, name='create_payment_intent'),
    path('create_monthly_subscription/', create_monthly_subscription, name='create_monthly_subscription'),
    path('payments/webhook/', webhook_handler, name='webhook'),
    path('cancel-subscription/<str:subscription_id>/', cancel_subscription, name='cancel_subscription'),
    path('', include(router.urls)),
] 