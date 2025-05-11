from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, ArticleViewSet, ProjectViewSet, DocumentViewSet, 
    EventViewSet, ImageViewSet, CotisationViewSet, LoginView, LogoutView,
    RefreshTokenView, UserStatsView, VerifyOTPView, Enable2FAView, Disable2FAView, Verify2FASetupView,
    PaymentViewSet, RegisterView, ApproveUserView,
    RequestPasswordResetView, ResetPasswordView, SetupPasswordView, payment_status
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.conf import settings

# Configuration du schéma Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="IYFFA API",
        default_version='v1',
        description="API Documentation for IYFFA Website",
        terms_of_service="https://www.iyffa.org/terms/",
        contact=openapi.Contact(email="contact@iyffa.org"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# Use DefaultRouter to automatically generate API endpoints
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'events', EventViewSet, basename='event')
router.register(r'images', ImageViewSet, basename='image')
router.register(r'cotisations', CotisationViewSet, basename='cotisation')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    # API endpoints from router
    path('', include(router.urls)),  # Include all registered API endpoints

    # Auth related URLs
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/refresh-token/', RefreshTokenView.as_view(), name='refresh-token'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('auth/verify-reset-code/', VerifyOTPView.as_view(), name='verify-reset-code'),
    
    # Registration and approval URLs
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/approve-user/<int:user_id>/', ApproveUserView.as_view(), name='approve-user'),
    path('auth/setup-password/', SetupPasswordView.as_view(), name='setup-password'),
    
    # Password reset URLs (consolidated)
    path('auth/request-password-reset/', RequestPasswordResetView.as_view(), name='request-password-reset'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    
    # 2FA management URLs
    path('auth/2fa/enable/', Enable2FAView.as_view(), name='enable-2fa'),
    path('auth/2fa/verify/', Verify2FASetupView.as_view(), name='verify-2fa-setup'),
    path('auth/2fa/disable/', Disable2FAView.as_view(), name='disable-2fa'),

    # User related URLs
    path('user/stats/', UserStatsView.as_view(), name='user-stats'),

    # Payment related URLs
    path('create_payment_intent/', PaymentViewSet.as_view({'post': 'create_intent'}), name='create-payment-intent'),
    path('create_monthly_subscription/', PaymentViewSet.as_view({'post': 'create_subscription'}), name='create-monthly-subscription'),
    path('webhook/', PaymentViewSet.as_view({'post': 'webhook'}), name='stripe-webhook'),
    path('cancel_subscription/<str:pk>/', PaymentViewSet.as_view({'post': 'cancel_subscription'}), name='cancel-subscription'),
    path('payment-status/', payment_status, name='payment-status'),
    path('membership_renewal_intent/', PaymentViewSet.as_view({'post': 'membership_renewal_intent'}), name='membership-renewal-intent'),

    # Documentation URLs
    path('docs/swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('docs/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('docs/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
