"""
Serializers for converting Django models to JSON and vice versa.
Handles data validation and format conversion for API endpoints.
"""

from rest_framework import serializers
from .models import User, Article, Project, Document, Event, Image, Cotisation, Payment

# This file converts Django model instances into JSON format to be used in the views

# User Serializer
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    Handles user profile data and authentication fields.
    """
    class Meta:
        model = User
        fields = '__all__'  # Includes all fields
        extra_kwargs = {'password': {'write_only': True}}  # Password is write-only

# Article Serializer
class ArticleSerializer(serializers.ModelSerializer):
    """
    Serializer for Article model.
    Handles article content and metadata.
    """
    class Meta:
        model = Article
        fields = '__all__'  # Includes all fields

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
    class Meta:
        model = Image
        fields = ['id', 'url', 'position']
        read_only_fields = ['id']

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
    Handles membership fee information.
    """
    class Meta:
        model = Cotisation
        fields = '__all__'

# Payment Serializer
class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for Payment model.
    Handles payment processing and tracking.
    """
    class Meta:
        model = Payment
        fields = '__all__'
