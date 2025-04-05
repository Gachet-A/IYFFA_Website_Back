from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, ArticleViewSet, ProjectViewSet, DocumentViewSet, 
    EventViewSet, ImageViewSet, CotisationViewSet, LoginView, LogoutView,
    RefreshTokenView, UserStatsView, VerifyOTPView, Enable2FAView, Disable2FAView, Verify2FASetupView
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

urlpatterns = [
    path('api/', include(router.urls)),  # Include all registered API endpoints

    # Auth related URLs
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # 2FA management URLs
    path('api/auth/2fa/enable/', Enable2FAView.as_view(), name='enable-2fa'),
    path('api/auth/2fa/verify/', Verify2FASetupView.as_view(), name='verify-2fa-setup'),
    path('api/auth/2fa/disable/', Disable2FAView.as_view(), name='disable-2fa'),

    # Swagger URLs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    path('logout/', LogoutView.as_view(), name='logout'),
    path('refresh-token/', RefreshTokenView.as_view(), name='refresh-token'),
    path('user-stats/', UserStatsView.as_view(), name='user-stats'),
]
