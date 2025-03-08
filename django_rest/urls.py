from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, ArticleViewSet, ProjectViewSet, DocumentViewSet, 
    EventViewSet, ImageViewSet, CotisationViewSet, PaymentViewSet,
    LoginView, VerifyOTPView, Enable2FAView, Disable2FAView
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
    path('api/', include(router.urls)),  # Include all registered API endpoints

    # Auth related URLs
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # 2FA management URLs
    path('api/auth/2fa/enable/', Enable2FAView.as_view(), name='enable-2fa'),
    path('api/auth/2fa/disable/', Disable2FAView.as_view(), name='disable-2fa'),
]
