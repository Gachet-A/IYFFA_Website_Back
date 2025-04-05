from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, create_payment_intent, webhook_handler

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('create_payment_intent/', create_payment_intent, name='create_payment_intent'),
    path('payments/webhook/', webhook_handler, name='webhook'),
    path('', include(router.urls)),
] 