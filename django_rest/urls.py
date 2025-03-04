from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, ArticleViewSet, ProjectViewSet, DocumentViewSet, 
    EventViewSet, ImageViewSet, CotisationViewSet, PaymentViewSet
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
]
