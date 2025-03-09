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
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count
from .models import User, Article, Project, Document, Event, Image, Cotisation, Payment
from .serializers import (
    UserSerializer, ArticleSerializer, ProjectSerializer, DocumentSerializer, 
    EventSerializer, ImageSerializer, CotisationSerializer, PaymentSerializer
)
from .permissions import IsAdminUser
from django.core.mail import send_mail
import random

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

class CotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user cotisations.
    Requires authentication for all operations.
    """
    queryset = Cotisation.objects.all()
    serializer_class = CotisationSerializer
    permission_classes = [IsAuthenticated]  # Keep this protected as it's sensitive data

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
    """Handle user login with optional 2FA"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Authenticate user and handle 2FA if enabled"""
        email = request.data.get("email")
        password = request.data.get("password")
        
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                if user.otp_enabled:
                    # Generate and send new OTP
                    otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    user.otp_secret = otp
                    user.save()
                    
                    # Send OTP via email
                    send_mail(
                        'Your Login Verification Code',
                        f'Your verification code is: {otp}\nEnter this code to complete your login.',
                        'noreply@iyffa.com',
                        [user.email],
                        fail_silently=False,
                    )
                    
                    return Response({
                        "otp_required": True,
                        "message": "Check your email for the verification code",
                        "user_type": user.user_type
                    }, status=200)
                
                refresh = RefreshToken.for_user(user)
                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user_type": user.user_type
                }, status=200)
            
        except User.DoesNotExist:
            pass
        
        return Response({"error": "Invalid credentials"}, status=401)

class VerifyOTPView(APIView):
    """Handle 2FA OTP verification at every login"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Verify email OTP and return JWT tokens if valid"""
        email = request.data.get("email")
        otp = request.data.get("otp")
        try:
            user = User.objects.get(email=email)
            
            # Verify OTP
            if otp == user.otp_secret:
                # Clear the used OTP
                user.otp_secret = None
                user.save()
                
                refresh = RefreshToken.for_user(user)
                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user_type": user.user_type
                }, status=200)
            else:
                return Response({"error": "Invalid verification code"}, status=400)
                
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

class Enable2FAView(APIView):
    """Enable two-factor authentication for a user"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Enable 2FA and send verification code via email"""
        user = request.user
        if user.otp_enabled:
            return Response({"error": "2FA is already enabled"}, status=400)
        
        # Generate a 6-digit OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Store OTP temporarily
        user.otp_secret = otp
        user.save()
        
        try:
            # Send OTP via email
            sent = send_mail(
                subject='Your 2FA Verification Code',
                message=f'Your verification code is: {otp}\nEnter this code to complete 2FA setup.',
                from_email=None,  # Will use DEFAULT_FROM_EMAIL from settings
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            if sent == 1:
                return Response({
                    "message": "2FA setup initiated. Check your email for the verification code.",
                    "next_step": "Verify this setup by making a POST request to /api/auth/2fa/verify/ with the code from your email"
                }, status=200)
            else:
                user.otp_secret = None
                user.save()
                return Response({
                    "error": "Failed to send verification code",
                    "message": "Please try again later"
                }, status=500)
                
        except Exception as e:
            user.otp_secret = None
            user.save()
            return Response({
                "error": str(e),
                "message": "Failed to send verification code. Please try again later."
            }, status=500)


class Verify2FASetupView(APIView):
    """Verify inital 2FA setup with email OTP to complete the setup"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Verify email OTP and complete 2FA setup"""
        user = request.user
        otp_code = request.data.get('otp')
        
        if not user.otp_secret:
            return Response({"error": "2FA setup not initiated"}, status=400)
            
        if user.otp_enabled:
            return Response({"error": "2FA is already enabled"}, status=400)
        
        # Verify OTP
        if otp_code == user.otp_secret:
            user.otp_enabled = True
            user.otp_secret = None  # Clear the temporary OTP
            user.save()
            return Response({
                "message": "2FA setup completed successfully",
                "status": "enabled"
            }, status=200)
        else:
            return Response({
                "error": "Invalid verification code",
                "message": "Please check the code from your email and try again"
            }, status=400)

class Disable2FAView(APIView):
    """Disable two-factor authentication for a user"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Disable 2FA for the current user"""
        user = request.user
        if not user.otp_enabled:
            return Response({"error": "2FA is not enabled"}, status=400)
        
        user.disable_2fa()
        return Response({"message": "2FA disabled successfully"}, status=200)
