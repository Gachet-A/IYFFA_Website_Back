"""
Django REST framework views for handling API endpoints.
Includes viewsets for all models and authentication views.
"""

from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Sum
from datetime import datetime, timedelta
from .models import User, Article, Project, Document, Event, Image, Cotisation, Payment
from .serializers import (
    UserSerializer, ArticleSerializer, ProjectSerializer, DocumentSerializer, 
    EventSerializer, ImageSerializer, CotisationSerializer, PaymentSerializer
)
from .permissions import IsAdminUser
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
import random
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import logging
from django.db import models
from django.utils import timezone

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Stripe with the secret key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY

def send_html_email(template_name, context, subject, recipient_list):
    """
    Send an HTML email using the specified template.
    
    Args:
        template_name: The name of the template to use (without .html)
        context: Dictionary of context variables for the template
        subject: Email subject
        recipient_list: List of recipient email addresses
    """
    try:
        # Render the HTML content
        html_content = render_to_string(f'emails/{template_name}.html', context)
        
        # Create the email message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=html_content,  # This will be the fallback for non-HTML email clients
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        msg.attach_alternative(html_content, "text/html")
        
        # Send the email
        msg.send()
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

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
        user = request.user

        # Vérifier que l'utilisateur est membre ou admin
        if not (user.user_type == 'user' or user.user_type == 'admin'):
            return Response({
                "error": "Unauthorized. Membership required.",
                "message": "Please contact an admin to become a member."
            }, status=status.HTTP_403_FORBIDDEN)

        # Stats pour les membres
        base_stats = {
            'personal_stats': {
                'my_articles': Article.objects.filter(user_id=user).count(),
                'my_events': Event.objects.filter(user_id=user).count(),
                # Ajoute ici d'autres stats personnelles si besoin
            },
            'recent_activities': {
                'articles': ArticleSerializer(
                    Article.objects.order_by('-creation_time')[:5],
                    many=True,
                    context={'request': request}
                ).data,
                'events': EventSerializer(
                    Event.objects.filter(
                        user_id=user
                    ).order_by('-start_datetime')[:5],
                    many=True,
                    context={'request': request}
                ).data,
                'projects': ProjectSerializer(
                    Project.objects.order_by('-id')[:5],
                    many=True,
                    context={'request': request}
                ).data
            }
        }

        # Stats admin
        if user.user_type == 'admin':
            thirty_days_ago = datetime.now() - timedelta(days=30)
            base_stats.update({
                'total_members': User.objects.filter(user_type='user').count(),
                'total_admins': User.objects.filter(user_type='admin').count(),
                'stripe_payments': {
                    'total_amount': float(Payment.objects.filter(status='succeeded').aggregate(total=Sum('amount'))['total'] or 0),
                    'count': Payment.objects.filter(status='succeeded').count(),
                    'recent': list(Payment.objects.filter(status='succeeded').order_by('-creation_time')[:5].values(
                        'amount', 'creation_time', 'status', 'currency', 'payment_type'
                    )),
                },
                
            })
            

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
    - Admins can see all projects
    - Members can see approved projects and their own projects
    - Non-members cannot access projects
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    
    def get_permissions(self):
        """Require authentication for all operations"""
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """Filter projects based on user permissions"""
        queryset = Project.objects.all()
        
        # If user is not authenticated, return empty queryset
        if not self.request.user.is_authenticated:
            return Project.objects.none()
            
        # If user is admin, show all projects
        if self.request.user.is_admin():
            return queryset.order_by('-created_at')
            
        # If user is a member, show approved projects and their own projects
        return queryset.filter(
            models.Q(status='approved') | 
            models.Q(user_id=self.request.user)
        ).order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new project proposal"""
        try:
            # Create project with initial status as 'pending'
            project_data = {
                'title': request.data.get('title'),
                'description': request.data.get('description'),
                'budget': request.data.get('budget'),
                'user_id': request.user,
                'status': 'pending'  # Initial status
            }
            
            # Handle document uploads if any
            documents = request.FILES.getlist('documents')
            document_positions = request.data.getlist('document_positions', [])
            
            # Create the project
            project = Project.objects.create(**project_data)
            
            # Create document records if any
            for doc, position in zip(documents, document_positions):
                Document.objects.create(
                    file=doc,
                    position=position,
                    project_id=project
                )
            
            # Send email to admin for approval
            admin_emails = User.objects.filter(
                user_type='admin'
            ).values_list('email', flat=True)
            
            if admin_emails:
                context = {
                    'project_title': project.title,
                    'project_description': project.description,
                    'project_budget': project.budget,
                    'proposer_name': f"{request.user.first_name} {request.user.last_name}",
                    'proposer_email': request.user.email,
                    'project_id': project.id
                }
                
                send_html_email(
                    template_name='project_proposal',
                    context=context,
                    subject=f'New Project Proposal: {project.title}',
                    recipient_list=list(admin_emails)
                )
            
            # Send confirmation email to the proposer
            proposer_context = {
                'name': f"{request.user.first_name} {request.user.last_name}",
                'project_title': project.title
            }
            
            send_html_email(
                template_name='project_proposal_confirmation',
                context=proposer_context,
                subject=f'Your Project Proposal: {project.title}',
                recipient_list=[request.user.email]
            )
            
            serializer = self.get_serializer(project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a project proposal (admin only)"""
        if not request.user.is_admin():
            return Response(
                {"error": "Only administrators can approve projects"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        project = self.get_object()
        project.status = 'approved'
        project.save()
        
        # Send email to project proposer
        context = {
            'name': f"{project.user_id.first_name} {project.user_id.last_name}",
            'project_title': project.title
        }
        
        send_html_email(
            template_name='project_approved',
            context=context,
            subject=f'Your Project "{project.title}" has been approved',
            recipient_list=[project.user_id.email]
        )
        
        return Response(
            {"message": "Project approved successfully"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a project proposal (admin only)"""
        if not request.user.is_admin():
            return Response(
                {"error": "Only administrators can reject projects"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        project = self.get_object()
        project.status = 'rejected'
        project.save()
        
        # Send email to project proposer
        context = {
            'name': f"{project.user_id.first_name} {project.user_id.last_name}",
            'project_title': project.title,
            'rejection_reason': request.data.get('reason', 'No reason provided')
        }
        
        send_html_email(
            template_name='project_rejected',
            context=context,
            subject=f'Your Project "{project.title}" has been rejected',
            recipient_list=[project.user_id.email]
        )
        
        return Response(
            {"message": "Project rejected successfully"},
            status=status.HTTP_200_OK
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update project and its documents"""
        try:
            project = self.get_object()
            
            # Update project fields
            project.title = request.data.get('title', project.title)
            project.description = request.data.get('description', project.description)
            project.budget = request.data.get('budget', project.budget)
            project.save()
            
            # Handle document updates
            existing_documents = request.data.getlist('existing_documents', [])
            new_documents = request.FILES.getlist('documents')
            document_positions = request.data.getlist('document_positions', [])
            
            # Delete documents that are not in existing_documents
            current_document_ids = [int(doc_id) for doc_id in existing_documents if doc_id]
            project.documents.exclude(id__in=current_document_ids).delete()
            
            # Add new documents
            for doc, position in zip(new_documents, document_positions):
                Document.objects.create(
                    file=doc,
                    position=position,
                    project_id=project
                )
            
            serializer = self.get_serializer(project)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        """Delete a project"""
        try:
            project = self.get_object()
            
            # Check if user is admin or project owner
            if not request.user.is_admin() and project.user_id != request.user:
                return Response(
                    {"error": "You don't have permission to delete this project"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Delete associated documents first
            project.documents.all().delete()
            
            # Delete the project
            project.delete()
            
            return Response(
                {"message": "Project deleted successfully"},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

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
    
    def post(self, request):
        """Authenticate user and handle 2FA"""
        email = request.data.get("email")
        password = request.data.get("password")
        
        if not email or not password:
            return Response(
                {"error": "Email and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            if not user.check_password(password):
                return Response(
                    {"error": "Invalid credentials"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
                if user.otp_enabled:
                # Generate new OTP
                    otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                
                # Update user's OTP
                    user.otp_secret = otp
                    user.save()
                    
                # Send OTP via email using HTML template
                context = {
                    'name': f"{user.first_name} {user.last_name}",
                    'otp': otp
                }
                
                send_html_email(
                    template_name='2fa_verification',
                    context=context,
                    subject='Your Login Verification Code',
                    recipient_list=[user.email]
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
                
            # If 2FA is not enabled, generate tokens directly
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
            
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

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
            # Send OTP via email using HTML template
            context = {
                'name': f"{user.first_name} {user.last_name}",
                'otp': otp
            }
            
            success = send_html_email(
                template_name='2fa_verification',
                context=context,
                subject='Your 2FA Setup Verification Code',
                recipient_list=[user.email]
            )
            
            if success:
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

# Payment related views
def send_payment_confirmation_email(payment_data):
    """
    Sends a confirmation email for successful payments.
    Handles different email templates based on payment type.
    """
    try:
        logger.info(f"Attempting to send payment confirmation email to {payment_data.get('email')}")
        logger.info(f"Payment data: {payment_data}")

        # Prepare the context for the template
        context = {
            'name': payment_data.get('name', 'Valued Donor'),
            'amount': payment_data.get('amount'),
            'currency': payment_data.get('currency'),
            'payment_type': payment_data.get('payment_type'),
            'cancel_url': payment_data.get('cancel_url')
        }

        # Send the HTML email
        success = send_html_email(
            template_name='payment_confirmation',
            context=context,
            subject=f"Thank you for your Gift!",
            recipient_list=[payment_data.get('email')]
        )

        if success:
            logger.info(f"Confirmation email sent successfully to {payment_data.get('email')}")
            return True
        else:
            logger.error(f"Failed to send confirmation email to {payment_data.get('email')}")
            return False

    except Exception as e:
        logger.error(f"Failed to send confirmation email: {str(e)}")
        logger.error(f"Payment data that caused the error: {payment_data}")
        logger.exception("Full traceback:")
        return False

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments and subscriptions.
    Handles payment intents, subscriptions, and webhooks.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create_intent', 'create_subscription', 'webhook']:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        """Filter payments to show only those belonging to the current user"""
        queryset = Payment.objects.all()
        
        # Always filter by the current user
        queryset = queryset.filter(user=self.request.user)
        
        # If filtering by subscription_id, add that filter
        subscription_id = self.request.query_params.get('subscription_id', None)
        if subscription_id:
            queryset = queryset.filter(subscription_id=subscription_id)
            
        return queryset

    @action(detail=False, methods=['post'])
    def create_intent(self, request):
        """Create a payment intent for one-time payments"""
        try:
            data = request.data
            amount = data.get('amount')
            email = data.get('email')
            name = data.get('name')
            payment_type = data.get('payment_type')
            payment_method_types = data.get('payment_method_types', ['card'])

            if not all([amount, email, payment_type]):
                return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

            if payment_type == 'membership_renewal' and not request.user.is_authenticated:
                return Response({'error': 'Authentication required for membership renewal'}, 
                              status=status.HTTP_401_UNAUTHORIZED)

            # Create payment intent for one-time payment
            payment_intent = stripe.PaymentIntent.create(
                amount=amount * 100,  # amount in cents
                currency='chf',
                payment_method_types=payment_method_types,
                metadata={
                    'payment_type': payment_type,
                    'name': name,
                    'email': email
                }
            )

            return Response({
                'clientSecret': payment_intent.client_secret,
                'payment_intent_id': payment_intent.id
            })

        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def create_subscription(self, request):
        """Create a monthly subscription"""
        try:
            data = request.data
            amount = data.get('amount')
            email = data.get('email')
            name = data.get('name')
            address = data.get('address')
            payment_type = 'monthly_donation'

            if not all([amount, email, name, address]):
                return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

            # Create or retrieve customer
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'payment_type': payment_type,
                    'name': name,
                    'address': address
                }
            )

            # Create price for subscription
            price = stripe.Price.create(
                unit_amount=amount * 100,
                currency='chf',
                recurring={'interval': 'month'},
                product_data={
                    'name': 'Monthly Donation',
                    'metadata': {
                        'payment_type': payment_type
                    }
                }
            )

            # Create setup intent for collecting payment method
            setup_intent = stripe.SetupIntent.create(
                customer=customer.id,
                payment_method_types=['card'],
                metadata={
                    'payment_type': payment_type,
                    'name': name,
                    'email': email,
                    'price_id': price.id,
                    'amount': amount,
                    'address': address
                }
            )

            return Response({
                'clientSecret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id,
                'customer_id': customer.id,
                'price_id': price.id
            })

        except Exception as e:
            logger.error(f"Error creating monthly subscription: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel_subscription(self, request, pk=None):
        """Cancel a subscription"""
        try:
            payment = self.get_object()
            if not payment.subscription_id:
                return Response(
                    {'error': 'No subscription found for this payment'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Cancel the subscription in Stripe
            subscription = stripe.Subscription.modify(
                payment.subscription_id,
                cancel_at_period_end=True
            )
            
            # Update the payment record
            payment.status = 'canceled'
            payment.save()
            
            return Response({
                'status': 'success',
                'message': 'Subscription will be canceled at the end of the current period'
            })
            
        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def webhook(self, request):
        """Handle Stripe webhook events"""
        payload = request.body
        sig_header = request.META['HTTP_STRIPE_SIGNATURE']
        event = None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            return HttpResponse(status=400)

        try:
            if event.type == 'setup_intent.succeeded':
                setup_intent = event.data.object
                customer_id = setup_intent.customer
                payment_method_id = setup_intent.payment_method
                
                # Attach payment method to customer
                stripe.PaymentMethod.attach(
                    payment_method_id,
                    customer=customer_id
                )
                
                # Set as default payment method
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={
                        'default_payment_method': payment_method_id
                    }
                )
                
                # Get price_id from metadata
                price_id = setup_intent.metadata.get('price_id')
                if not price_id:
                    logger.error("No price_id found in setup intent metadata")
                    return HttpResponse(status=200)
                
                # Create subscription
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'price': price_id}],
                    payment_behavior='default_incomplete'
                )
                
                # Create payment record
                Payment.objects.create(
                    stripe_payment_id=setup_intent.id,
                    amount=int(float(setup_intent.metadata.get('amount', 0)) * 100),
                    currency='chf',
                    status='succeeded',
                    payment_type='monthly_donation',
                    payment_method='card',
                    subscription_id=subscription.id,
                    user=request.user if request.user.is_authenticated else None
                )
                
                # Send confirmation email
                send_payment_confirmation_email({
                    'email': setup_intent.metadata.get('email'),
                    'name': setup_intent.metadata.get('name'),
                    'amount': setup_intent.metadata.get('amount'),
                    'payment_type': 'monthly_donation',
                    'cancel_url': f"http://localhost:8080/cancel_subscription/{subscription.id}",
                    'currency': 'chf',
                    'payment_method': 'card'
                })
                
                return HttpResponse(status=200)

            elif event.type == 'payment_intent.succeeded':
                payment_intent = event.data.object
                email = payment_intent.receipt_email or payment_intent.metadata.get('email')
                
                if not email:
                    logger.warning("No email found in payment intent, skipping payment record creation")
                    return HttpResponse(status=200)

                # Get the payment method used
                payment_method = stripe.PaymentMethod.retrieve(payment_intent.payment_method)
                payment_method_type = payment_method.type

                # Create payment record
                payment_data = {
                    'stripe_payment_id': payment_intent.id,
                    'amount': payment_intent.amount / 100,
                    'currency': payment_intent.currency,
                    'status': 'succeeded',
                    'payment_type': payment_intent.metadata.get('payment_type', 'one_time_donation'),
                    'payment_method': payment_method_type
                }
                Payment.objects.create(**payment_data)

                # Send confirmation email
                email_data = {
                    'stripe_id': payment_intent.id,
                    'amount': payment_intent.amount / 100,
                    'currency': payment_intent.currency,
                    'email': email,
                    'name': payment_intent.metadata.get('name', 'Anonymous'),
                    'payment_type': payment_intent.metadata.get('payment_type', 'one_time_donation'),
                    'payment_method': payment_method_type
                }
                send_payment_confirmation_email(email_data)

            elif event.type == 'customer.subscription.deleted':
                subscription = event.data.object
                payment = Payment.objects.filter(subscription_id=subscription.id).first()
            if payment:
                    payment.status = 'canceled'
                    payment.save()

            return HttpResponse(status=200)

        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return HttpResponse(status=500)

class RegisterView(APIView):
    """Handle user registration with email verification"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Register a new user with pending status"""
        try:
            # Generate a random password for the inactive user
            random_password = ''.join([str(random.randint(0, 9)) for _ in range(12)])
            
            # Prepare data for serializer
            data = {
                'email': request.data.get('email'),
                'first_name': request.data.get('name'),
                'last_name': request.data.get('surname'),
                'birthdate': request.data.get('dateOfBirth'),
                'phone_number': request.data.get('phone'),
                'status': False,  # Inactive by default
                'user_type': 'user',
                'cgu': request.data.get('acceptTerms1', False),
                'password': random_password
            }
            
            # Validate required fields
            required_fields = ['email', 'first_name', 'last_name', 'birthdate', 'phone_number']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if email already exists
            if User.objects.filter(email=data['email']).exists():
                return Response(
                    {'error': 'A user with this email already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use the serializer to create the user
            serializer = UserSerializer(data=data)
            if serializer.is_valid():
                user = serializer.save()
                
                # Send email to admins
                admin_emails = User.objects.filter(
                    user_type='admin'
                ).values_list('email', flat=True)
                
                if admin_emails:
                    context = {
                        'user_name': f"{user.first_name} {user.last_name}",
                        'user_email': user.email,
                        'user_phone': user.phone_number,
                        'user_birthdate': user.birthdate,
                        'user_id': user.id
                    }
                    
                    send_html_email(
                        template_name='new_registration',
                        context=context,
                        subject=f'New User Registration: {user.email}',
                        recipient_list=list(admin_emails)
                    )
                
                return Response({
                    "message": "Registration successful. Please wait for admin approval.",
                    "user_id": user.id
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            logger.error(f"Error in user registration: {str(e)}")
            return Response(
                {'error': 'An error occurred during registration. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

class ApproveUserView(APIView):
    """Handle user approval and password setup"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        """Approve a user and send password setup email"""
        try:
            user = get_object_or_404(User, id=user_id)
            
            if user.status:
                return Response(
                    {'error': 'User is already active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate a temporary token for password setup
            token = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.otp_secret = token
            user.save()
            
            # Send password setup email
            context = {
                'name': f"{user.first_name} {user.last_name}",
                'token': token,
                'email': user.email
            }
            
            success = send_html_email(
                template_name='setup_password',
                context=context,
                subject='Complete Your Registration',
                recipient_list=[user.email]
            )
            
            if not success:
                # Revert token if email sending fails
                user.otp_secret = None
                user.save()
                return Response(
                    {'error': 'Failed to send password setup email'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Activate the user
            user.status = True
            user.save()
            
            # Log the approval
            logger.info(f"User {user.email} approved by admin {request.user.email}")
            
            return Response({
                "message": "User approved successfully. Password setup email sent.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": f"{user.first_name} {user.last_name}",
                    "status": user.status
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in user approval: {str(e)}")
            return Response(
                {'error': 'An error occurred during user approval. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

class RequestPasswordResetView(APIView):
    """Handle password reset requests"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Send password reset email"""
        try:
            email = request.data.get('email')
            if not email:
                return Response(
                    {'error': 'Email is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Don't reveal that the user doesn't exist
                return Response({
                    'message': 'If an account exists with this email, you will receive a password reset link.'
                })
            
            # Generate a temporary token for password reset
            token = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.otp_secret = token
            user.otp_secret_created_at = datetime.now()
            user.save()
            
            # Send password reset email
            context = {
                'name': f"{user.first_name} {user.last_name}",
                'token': token,
                'email': user.email
            }
            
            success = send_html_email(
                template_name='reset_password',
                context=context,
                subject='Reset Your Password',
                recipient_list=[user.email]
            )
            
            if not success:
                # Revert token if email sending fails
                user.otp_secret = None
                user.otp_secret_created_at = None
                user.save()
                return Response(
                    {'error': 'Failed to send password reset email'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                'message': 'If an account exists with this email, you will receive a password reset link.'
            })
            
        except Exception as e:
            logger.error(f"Error in password reset request: {str(e)}")
            return Response(
                {'error': 'An error occurred. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

class ResetPasswordView(APIView):
    """Handle password reset with token verification"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Validate reset token"""
        try:
            token = request.query_params.get('token')
            email = request.query_params.get('email')
            
            if not token or not email:
                return Response(
                    {'error': 'Token and email are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Invalid reset link'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if token exists and matches
            if not user.otp_secret or user.otp_secret != token:
                return Response(
                    {'error': 'Invalid or expired token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if token is expired (30 minutes)
            if not user.otp_secret_created_at or (timezone.now() - user.otp_secret_created_at) > timedelta(minutes=30):
                # Clear expired token
                user.otp_secret = None
                user.otp_secret_created_at = None
                user.save()
                return Response(
                    {'error': 'Token has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({'valid': True})
            
        except Exception as e:
            logger.error(f"Error validating reset token: {str(e)}")
            return Response(
                {'error': 'An error occurred while validating the reset link'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def post(self, request):
        """Verify token and set new password"""
        try:
            email = request.data.get('email')
            token = request.data.get('token')
            new_password = request.data.get('password')
            
            if not all([email, token, new_password]):
                return Response(
                    {'error': 'Missing required fields'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate password strength - only check length and numbers
            if len(new_password) < 8:
                return Response(
                    {'error': 'Password must be at least 8 characters long'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not any(char.isdigit() for char in new_password):
                return Response(
                    {'error': 'Password must contain at least one number'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = get_object_or_404(User, email=email)
            
            # Check if token exists and matches
            if not user.otp_secret or user.otp_secret != token:
                return Response(
                    {'error': 'Invalid or expired token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if token is expired (30 minutes)
            if not user.otp_secret_created_at or (timezone.now() - user.otp_secret_created_at) > timedelta(minutes=30):
                # Clear expired token
                user.otp_secret = None
                user.otp_secret_created_at = None
                user.save()
                return Response(
                    {'error': 'Token has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password and clear token
            user.set_password(new_password)
            user.otp_secret = None
            user.otp_secret_created_at = None
            user.save()
            
            # Log successful password reset
            logger.info(f"Password reset completed for user {user.email}")
            
            return Response({
                "message": "Password reset successful. You can now log in with your new password."
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in password reset: {str(e)}")
            return Response(
                {'error': 'An error occurred during password reset. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

class SetupPasswordView(APIView):
    """Handle password setup after user approval"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Set up password for newly approved user"""
        try:
            email = request.data.get('email')
            token = request.data.get('token')
            new_password = request.data.get('password')
            
            if not all([email, token, new_password]):
                return Response(
                    {'error': 'Missing required fields'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate password strength - only check length and numbers
            if len(new_password) < 8:
                return Response(
                    {'error': 'Password must be at least 8 characters long'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not any(char.isdigit() for char in new_password):
                return Response(
                    {'error': 'Password must contain at least one number'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = get_object_or_404(User, email=email)
            
            # Check if token exists and matches
            if not user.otp_secret or user.otp_secret != token:
                return Response(
                    {'error': 'Invalid or expired token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password and clear token
            user.set_password(new_password)
            user.otp_secret = None
            user.save()
            
            # Log successful password setup
            logger.info(f"Password setup completed for user {user.email}")
            
            return Response({
                "message": "Password setup successful. You can now log in with your new password."
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in password setup: {str(e)}")
            return Response(
                {'error': 'An error occurred during password setup. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )
