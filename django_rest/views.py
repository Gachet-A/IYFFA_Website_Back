"""
Django REST framework views for handling API endpoints.
Includes viewsets for all models and authentication views.
"""

from django.shortcuts import render
from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count
from .models import User, Article, Project, Document, Event, Image, Cotisation, Payment
from .serializers import (
    UserSerializer, ArticleSerializer, ProjectSerializer, DocumentSerializer, 
    EventSerializer, ImageSerializer, CotisationSerializer, PaymentSerializer
)
from .permissions import IsAdminUser

# User ViewSet: Standard CRUD operations
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users.
    Only accessible by admin users.
    Provides CRUD operations and statistics endpoint.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get system-wide statistics for admin dashboard"""
        if not request.user.is_admin():
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        stats = {
            'total_users': User.objects.count(),
            'total_regular_users': User.objects.filter(usr_type='user').count(),
            'total_articles': Article.objects.count(),
            'total_events': Event.objects.count(),
            'total_projects': Project.objects.count(),
            'recent_activities': {
                'articles': Article.objects.order_by('-art_creation_time')[:5],
                'events': Event.objects.order_by('-eve_date')[:5],
                'projects': Project.objects.all()[:5]
            }
        }
        return Response(stats)

# Article ViewSet: Standard CRUD operations
class ArticleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing articles.
    Public read access, authenticated write access.
    """
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    
    def get_permissions(self):
        """Require authentication only for write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        """Automatically set the current user as the article author"""
        serializer.save(art_user_id=self.request.user)

# Project ViewSet: Standard CRUD operations
class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing projects.
    Public read access, authenticated write access.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    
    def get_permissions(self):
        """Require authentication only for write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        """Automatically set the current user as the project owner"""
        serializer.save(pro_user_id=self.request.user)

# Document ViewSet: Standard CRUD operations
class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project documents.
    Public read access, authenticated write access.
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    
    def get_permissions(self):
        """Require authentication only for write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

# Event ViewSet: Standard CRUD operations
class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing events.
    Public read access, authenticated write access.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    
    def get_permissions(self):
        """Require authentication only for write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        """Automatically set the current user as the event organizer"""
        serializer.save(eve_user_id=self.request.user)

# Image ViewSet: Standard CRUD operations
class ImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing event images.
    Public read access, authenticated write access.
    """
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    
    def get_permissions(self):
        """Require authentication only for write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

# Cotisation ViewSet: Standard CRUD operations
class CotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user cotisations.
    Requires authentication for all operations.
    """
    queryset = Cotisation.objects.all()
    serializer_class = CotisationSerializer
    permission_classes = [IsAuthenticated]  # Keep this protected as it's sensitive data

# Payment ViewSet: Standard CRUD operations
class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.
    Requires authentication for all operations.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]  # Keep this protected as it's sensitive data

## Auth related views
class LoginView(APIView):
    """
    Handle user login with optional 2FA.
    Returns JWT tokens upon successful authentication.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Authenticate user and handle 2FA if enabled.
        Returns JWT tokens or 2FA challenge.
        """
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(request, email=email, password=password)

        if user:
            if user.usr_otp_enabled:
                otp_device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
                if otp_device:
                    otp_device.generate_challenge()
                    return Response({
                        "otp_required": True, 
                        "message": "Enter OTP",
                        "user_type": user.usr_type
                    }, status=200)
            
            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_type": user.usr_type
            }, status=200)

        return Response({"error": "Invalid credentials"}, status=401)
    
class VerifyOTPView(APIView):
    """Handle 2FA OTP verification"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Verify OTP and return JWT tokens if valid"""
        email = request.data.get("email")
        otp = request.data.get("otp")
        try:
            user = User.objects.get(usr_email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        if user.verify_otp(otp):
            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_type": user.usr_type
            }, status=200)
        else:
            return Response({"error": "Invalid OTP"}, status=400)

class Enable2FAView(APIView):
    """Enable two-factor authentication for a user"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Enable 2FA and return the OTP secret"""
        user = request.user
        if user.usr_otp_enabled:
            return Response({"error": "2FA is already enabled"}, status=400)
        
        otp_secret = user.enable_2fa()
        return Response({
            "message": "2FA enabled successfully",
            "otp_secret": otp_secret
        }, status=200)

class Disable2FAView(APIView):
    """Disable two-factor authentication for a user"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Disable 2FA for the current user"""
        user = request.user
        if not user.usr_otp_enabled:
            return Response({"error": "2FA is not enabled"}, status=400)
        
        user.disable_2fa()
        return Response({"message": "2FA disabled successfully"}, status=200)
