"""
Serializers for converting Django models to JSON and vice versa.
Handles data validation and format conversion for API endpoints.
"""

from rest_framework import serializers
from .models import User, Article, Project, Document, Event, Image, Cotisation, Payment
from django.contrib.auth.hashers import make_password

# This file converts Django model instances into JSON format to be used in the views

# User Serializer
# Liste explicite des champs autorisés
# Gestion sécurisée du mot de passe (hachage), Champs en lecture seule pour les données sensibles
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    Handles user profile data and authentication fields.
    """
    password = serializers.CharField(write_only=True, required=False)
    username = serializers.CharField(required=False, write_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'birthdate',
            'phone_number', 'user_type', 'status', 'cgu',
            'stripe_id', 'otp_enabled', 'date_joined', 'password',
            'username'
        ]
        read_only_fields = ['id', 'date_joined', 'stripe_id']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'birthdate': {'required': True},
            'phone_number': {'required': True},
            'user_type': {'required': False},  # On rend le champ optionnel
            'status': {'required': True},
            'cgu': {'required': True},
        }

    def validate(self, data):
        """Validate user data"""
        # Pour la création d'utilisateur, le mot de passe est requis
        if not self.instance and 'password' not in data:
            raise serializers.ValidationError({"password": "Password is required for new users"})

        # Validation du user_type
        if 'user_type' in data:
            # S'assurer que le type est valide
            if data['user_type'] not in ['admin', 'user']:
                raise serializers.ValidationError({"user_type": "Invalid user type"})

        return data

    def create(self, validated_data):
        """Handle user creation with password hashing"""
        # Utiliser l'email comme username
        validated_data['username'] = validated_data.get('email')
        
        # Par défaut, le type est 'user' si non spécifié
        if 'user_type' not in validated_data:
            validated_data['user_type'] = 'user'
        
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
            
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Handle user update with password hashing if provided"""
        # Mettre à jour le username si l'email change
        if 'email' in validated_data:
            validated_data['username'] = validated_data['email']
            
        if 'password' in validated_data and validated_data['password']:
            validated_data['password'] = make_password(validated_data['password'])
        elif 'password' in validated_data:
            del validated_data['password']

        # Conserver le type d'utilisateur actuel si non spécifié
        if 'user_type' not in validated_data:
            validated_data['user_type'] = instance.user_type
            
        return super().update(instance, validated_data)

# Article Serializer
class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for articles with author details"""
    author_name = serializers.SerializerMethodField()
    author_title = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ['id', 'title', 'text', 'creation_time', 'user_id', 
                 'author_name', 'author_title', 'formatted_date']
        read_only_fields = ['id', 'user_id', 'creation_time']

    def get_author_name(self, obj):
        return f"{obj.user_id.first_name} {obj.user_id.last_name}"

    def get_author_title(self, obj):
        return "Admin" if obj.user_id.is_admin() else "Member"

    def get_formatted_date(self, obj):
        return obj.creation_time.strftime("%B %d, %Y")

# Project Serializer
class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for Project model.
    Handles project details and budget information.
    """
    class Meta:
        model = Project
        fields = '__all__'

# Document Serializer
class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for Document model.
    Handles project document metadata.
    """
    class Meta:
        model = Document
        fields = '__all__'
        
# Image Serializer
class ImageSerializer(serializers.ModelSerializer):
    """Serializer for event images"""
    img_url = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['id', 'img_url', 'position']
        read_only_fields = ['id']

    def get_img_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            return request.build_absolute_uri(obj.file.url)
        return None

# Event Serializer
class EventSerializer(serializers.ModelSerializer):
    """Serializer for events with nested images"""
    images = ImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    image_positions = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 
            'start_datetime', 'end_datetime',
            'location', 'price', 'user_id',
            'images', 'uploaded_images', 'image_positions'
        ]
        read_only_fields = ['id', 'user_id']

    def create(self, validated_data):
        """Handle event creation with images"""
        uploaded_images = validated_data.pop('uploaded_images', [])
        image_positions = validated_data.pop('image_positions', [])
        
        # Create event
        event = Event.objects.create(**validated_data)
        
        # Create images
        for image, position in zip(uploaded_images, image_positions):
            Image.objects.create(
                url=image,
                position=position,
                event_id=event
            )
        
        return event

    def update(self, instance, validated_data):
        """Handle event update with images"""
        uploaded_images = validated_data.pop('uploaded_images', None)
        image_positions = validated_data.pop('image_positions', None)
        
        # Update event fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle image updates if new images are provided
        if uploaded_images is not None:
            # Delete existing images
            instance.images.all().delete()
            
            # Create new images
            for image, position in zip(uploaded_images, image_positions):
                Image.objects.create(
                    url=image,
                    position=position,
                    event_id=instance
                )
        
        return instance

# Cotisation Serializer
class CotisationSerializer(serializers.ModelSerializer):
    """
    Serializer for Cotisation model.
    Handles membership fee details.
    """
    class Meta:
        model = Cotisation
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'cotisation', 'stripe_payment_id', 'amount', 
            'currency', 'status', 'payment_type', 'payment_method', 
            'transaction_id', 'description', 'subscription_id', 
            'creation_time', 'update_time', 'receipt_pdf_path'
        ]
        read_only_fields = ['id', 'creation_time', 'update_time']
