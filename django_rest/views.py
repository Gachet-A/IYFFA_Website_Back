"""
Django REST framework views for handling API endpoints.
Includes viewsets for all models and authentication views.
"""

from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Sum
from datetime import datetime, timedelta
from .models import User, Article, Project, Document, Event, Image, Cotisation
from .serializers import (
    UserSerializer, ArticleSerializer, ProjectSerializer, DocumentSerializer, 
    EventSerializer, ImageSerializer, CotisationSerializer
)
from .permissions import IsAdminUser
from django.core.mail import send_mail
import random
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_stripe_payments.models import Payment  # Import the new Payment model

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users.
    Only accessible by admin users.
    Provides CRUD operations and statistics endpoint.
    Dashboard stats accessible by members only.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        """
        Require admin permissions for most operations,
        but allow member access to dashboard_stats
        """
        if self.action == 'dashboard_stats':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]

    @swagger_auto_schema(
        operation_description="Liste tous les utilisateurs",
        responses={
            200: UserSerializer(many=True),
            401: "Non authentifié",
            403: "Non autorisé"
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Crée un nouvel utilisateur",
        request_body=UserSerializer,
        responses={
            201: UserSerializer,
            400: "Données invalides",
            401: "Non authentifié",
            403: "Non autorisé"
        }
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new user with proper validation"""
        try:
            # Vérifier si l'email existe déjà
            email = request.data.get('email')
            if email and User.objects.filter(email=email).exists():
                return Response(
                    {'error': 'Un utilisateur avec cet email existe déjà'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Forcer le username à être l'email
            request.data['username'] = email

            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Créer l'utilisateur
            user = serializer.save()
            
            # Retourner la réponse sans le mot de passe
            response_serializer = self.get_serializer(user)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            print(f"Error creating user: {str(e)}")  # Log l'erreur pour le débogage
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_description="Met à jour un utilisateur existant",
        request_body=UserSerializer,
        responses={
            200: UserSerializer,
            400: "Données invalides",
            401: "Non authentifié",
            403: "Non autorisé",
            404: "Utilisateur non trouvé"
        }
    )
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update user with proper validation"""
        try:
            instance = self.get_object()
            partial = kwargs.pop('partial', False)
            
            # Vérifier si l'email est modifié et existe déjà
            email = request.data.get('email')
            if email and email != instance.email and User.objects.filter(email=email).exists():
                return Response(
                    {'error': 'Un utilisateur avec cet email existe déjà'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Si l'email est modifié, mettre à jour aussi le username
            if email:
                request.data['username'] = email

            # Vérifier si on essaie de changer le type d'utilisateur
            new_user_type = request.data.get('user_type')
            if new_user_type:
                # Compter le nombre total d'administrateurs
                admin_count = User.objects.filter(user_type='admin').count()
                
                # Si on essaie de rétrograder un admin en utilisateur
                if instance.user_type == 'admin' and new_user_type == 'user':
                    if admin_count <= 1:
                        return Response(
                            {'error': 'Impossible de changer le type. Il doit rester au moins un administrateur.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            serializer = self.get_serializer(
                instance,
                data=request.data,
                partial=partial
            )
            if not serializer.is_valid():
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mettre à jour l'utilisateur
            user = serializer.save()
            
            # Retourner la réponse
            response_serializer = self.get_serializer(user)
            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            print(f"Error updating user: {str(e)}")  # Log l'erreur pour le débogage
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_description="Supprime un utilisateur",
        responses={
            204: "Suppression réussie",
            401: "Non authentifié",
            403: "Non autorisé",
            404: "Utilisateur non trouvé"
        }
    )
    def destroy(self, request, *args, **kwargs):
        """Delete user with proper validation"""
        try:
            instance = self.get_object()
            
            # Empêcher la suppression de son propre compte
            if instance == request.user:
                return Response(
                    {'error': "Vous ne pouvez pas supprimer votre propre compte"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Supprimer l'utilisateur
            instance.delete()
            return Response(
                {"message": "Utilisateur supprimé avec succès"},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_description="Récupère les statistiques du système",
        responses={
            200: openapi.Response(
                description="Statistiques du système",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_users': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_regular_users': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_articles': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_events': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_projects': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            403: "Non autorisé"
        }
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get system-wide statistics for admin dashboard"""
        if request.user.user_type != 'admin':
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        stats = {
            'total_users': User.objects.count(),
            'total_regular_users': User.objects.filter(user_type='user').count(),
            'total_articles': Article.objects.count(),
            'total_events': Event.objects.count(),
            'total_projects': Project.objects.count(),
            'recent_activities': {
                'articles': ArticleSerializer(
                    Article.objects.order_by('-creation_time')[:5],
                    many=True
                ).data,
                'events': EventSerializer(
                    Event.objects.order_by('-start_datetime')[:5],
                    many=True
                ).data,
                'projects': ProjectSerializer(
                    Project.objects.all()[:5],
                    many=True
                ).data
            }
        }
        return Response(stats)

    @swagger_auto_schema(
        operation_description="Récupère les statistiques du tableau de bord",
        responses={
            200: openapi.Response(
                description="Statistiques du tableau de bord",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'has_active_membership': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'error': openapi.Schema(type=openapi.TYPE_STRING),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            403: "Non autorisé"
        }
    )
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for members"""
        user = request.user
        
        # Vérifier si l'utilisateur a un paiement de cotisation valide
        has_active_membership = Payment.objects.filter(
            cot_id__user_id=user,
            status='succeeded'
        ).exists()
        
        if not has_active_membership and not user.is_admin():
            return Response({
                "error": "Unauthorized. Active membership required.",
                "message": "Please subscribe to access the dashboard."
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Stats pour les membres
        base_stats = {
            'personal_stats': {
                'my_articles': Article.objects.filter(user_id=user).count(),
                'my_events': Event.objects.filter(user_id=user).count(),
                'my_payments': list(Payment.objects.filter(
                    cot_id__user_id=user
                ).order_by('-creation_time')[:5].values(
                    'amount', 'creation_time', 'status', 'currency'
                )),
                'membership_status': {
                    'is_active': has_active_membership,
                    'current_cotisation': CotisationSerializer(
                        Cotisation.objects.filter(
                            user_id=user,
                            payment__status='succeeded'
                        ).order_by('-id').first(),
                        context={'request': request}
                    ).data if Cotisation.objects.filter(user_id=user, payment__status='succeeded').exists() else None
                }
            },
            'recent_activities': {
                'articles': ArticleSerializer(
                    Article.objects.order_by('-creation_time')[:5],
                    many=True,
                    context={'request': request}
                ).data,
                'events': EventSerializer(
                    Event.objects.filter(
                        start_datetime__gte=datetime.now()
                    ).order_by('start_datetime')[:5],
                    many=True,
                    context={'request': request}
                ).data
            }
        }

        # Stats supplémentaires pour les admins
        if user.is_admin():
            # Calcul des statistiques sur 30 jours
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            # Calcul des paiements sur 30 jours
            monthly_payments = Payment.objects.filter(
                creation_time__gte=thirty_days_ago,
                status='succeeded'
            ).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            admin_stats = {
                'total_users': User.objects.count(),
                'total_regular_users': User.objects.filter(user_type='user').count(),
                'total_active_members': User.objects.filter(
                    cotisation__payment__status='succeeded'
                ).distinct().count(),
                'payment_stats': {
                    'total_amount': Payment.objects.filter(
                        status='succeeded'
                    ).aggregate(total=Sum('amount'))['total'] or 0,
                    'monthly_amount': monthly_payments,
                    'recent_payments': list(Payment.objects.filter(
                        status='succeeded'
                    ).order_by('-creation_time')[:5].values(
                        'amount', 'creation_time', 'status', 'currency'
                    ))
                },
                'user_growth': {
                    'monthly_new_users': User.objects.filter(
                        date_joined__gte=thirty_days_ago
                    ).count(),
                    'monthly_new_members': Cotisation.objects.filter(
                        payment__creation_time__gte=thirty_days_ago,
                        payment__status='succeeded'
                    ).values('user_id').distinct().count()
                }
            }
            base_stats.update(admin_stats)
            
        return Response(base_stats)


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

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create article with user association"""
        try:
            article_data = {
                'title': request.data.get('title'),
                'text': request.data.get('text'),
                'user_id': request.user
            }
            
            article = Article.objects.create(**article_data)
            serializer = self.get_serializer(article)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        """Delete an article"""
        try:
            article = self.get_object()
            
            # Check if user is admin or article author
            if not request.user.is_admin() and article.user_id != request.user:
                return Response(
                    {"error": "You don't have permission to delete this article"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            article.delete()
            return Response(
                {"message": "Article deleted successfully"},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

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
    Handles event creation with multiple images.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    
    def get_permissions(self):
        """Require authentication only for write operations"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create event with multiple images"""
        try:
            # Create event
            event_data = {
                'title': request.data.get('title'),
                'description': request.data.get('description'),
                'start_datetime': request.data.get('start_datetime'),
                'location': request.data.get('location'),
                'price': request.data.get('price'),
                'user_id': request.user
            }
            
            # Handle end_datetime separately
            end_datetime = request.data.get('end_datetime')
            if end_datetime and end_datetime != "":
                event_data['end_datetime'] = end_datetime
            
            event = Event.objects.create(**event_data)
            
            # Handle images
            images = request.FILES.getlist('images')
            image_positions = request.data.getlist('image_positions')
            
            for image, position in zip(images, image_positions):
                Image.objects.create(
                    file=image,
                    position=position,
                    event_id=event
                )
            
            serializer = self.get_serializer(event)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update event and its images"""
        try:
            event = self.get_object()
            
            # Update event fields
            event.title = request.data.get('title', event.title)
            event.description = request.data.get('description', event.description)
            event.start_datetime = request.data.get('start_datetime', event.start_datetime)
            
            # Handle end_datetime specifically
            end_datetime = request.data.get('end_datetime')
            if end_datetime == "":
                event.end_datetime = None  # Set to None when empty string is received
            elif end_datetime:
                event.end_datetime = end_datetime
            
            event.location = request.data.get('location', event.location)
            event.price = request.data.get('price', event.price)
            event.save()
            
            # Handle new images if any
            if 'images' in request.FILES:
                # Delete existing images
                event.images.all().delete()
                
                # Add new images
                images = request.FILES.getlist('images')
                image_positions = request.data.getlist('image_positions', [str(i) for i in range(len(images))])
                for image, position in zip(images, image_positions):
                    Image.objects.create(
                        file=image,
                        position=position,
                        event_id=event
                    )
            
            serializer = self.get_serializer(event)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['delete'])
    def delete_image(self, request, pk=None):
        """Delete a specific image from an event"""
        event = self.get_object()
        image_id = request.data.get('image_id')
        
        if not image_id:
            return Response(
                {'error': 'Image ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            image = Image.objects.get(id=image_id, event_id=event)
            image.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Image.DoesNotExist:
            return Response(
                {'error': 'Image not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, *args, **kwargs):
        """Delete an event and its associated images"""
        try:
            event = self.get_object()
            
            # Optional: Add additional permission check
            if not request.user.is_admin() and event.user_id != request.user:
                return Response(
                    {"error": "You don't have permission to delete this event"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Delete associated images first
            event.images.all().delete()
            
            # Delete the event
            event.delete()
            
            return Response(
                {"message": "Event deleted successfully"},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        
    def create(self, request, *args, **kwargs):
        """Create a new image for an event"""
        try:
            event_id = request.data.get('event_id')
            if not event_id:
                return Response(
                    {'error': 'Event ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            event = get_object_or_404(Event, id=event_id)
            
            image = Image.objects.create(
                file=request.FILES['image'],
                position=request.data.get('position', 0),
                event_id=event
            )
            
            serializer = self.get_serializer(image)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class CotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user cotisations.
    Requires authentication for all operations.
    """
    queryset = Cotisation.objects.all()
    serializer_class = CotisationSerializer
    permission_classes = [IsAuthenticated]  # Keep this protected as it's sensitive data

## Auth related views
class LoginView(APIView):
    """Handle user login with optional 2FA"""
    permission_classes = [AllowAny]
    
    @transaction.atomic
    def post(self, request):
        """Authenticate user and handle 2FA"""
        email = request.data.get("email")
        password = request.data.get("password")
        
        try:
            user = User.objects.get(email=email)
            
            if user.check_password(password):
                if user.otp_enabled:
                    # Generate new OTP
                    otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    
                    # Update user's OTP
                    User.objects.filter(id=user.id).update(otp_secret=otp)
                    
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
                        "user": {
                            "id": user.id,
                            "email": user.email,
                            "name": user.first_name,
                            "surname": user.last_name,
                            "user_type": user.user_type
                        }
                    })
                
                refresh = RefreshToken.for_user(user)
                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "name": user.first_name,
                        "surname": user.last_name,
                        "user_type": user.user_type
                    }
                })
            
            return Response({"error": "Invalid credentials"}, status=401)
            
        except User.DoesNotExist:
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
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "name": user.first_name,
                        "surname": user.last_name,
                        "user_type": user.user_type
                    }
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
        user = request.user
        if not user.otp_enabled:
            return Response(
                {'error': 'Two-factor authentication is not enabled for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.otp_enabled = False
        user.save()
        
        return Response(
            {'message': 'Two-factor authentication has been disabled'},
            status=status.HTTP_200_OK
        )

class LogoutView(APIView):
    """Handle user logout by blacklisting the refresh token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'message': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class RefreshTokenView(APIView):
    """Handle token refresh for authenticated users"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            access_token = str(token.access_token)
            
            return Response({
                'access': access_token,
                'refresh': str(token)
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class UserStatsView(APIView):
    """Get user statistics for the dashboard"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get user's active cotisation
        active_cotisation = Cotisation.objects.filter(
            user_id=user,
            end_date__gte=datetime.now()
        ).first()
        
        # Get user's payment history
        payments = Payment.objects.filter(user_id=user).order_by('-creation_time')
        
        # Get user's event participation
        events_participated = Event.objects.filter(
            participants=user
        ).count()
        
        return Response({
            'has_active_membership': bool(active_cotisation),
            'membership_end_date': active_cotisation.end_date if active_cotisation else None,
            'total_payments': payments.count(),
            'recent_payments': [
                {
                    'amount': payment.amount,
                    'date': payment.creation_time,
                    'status': payment.status
                } for payment in payments[:5]
            ],
            'events_participated': events_participated
        })
