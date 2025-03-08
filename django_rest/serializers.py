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

# Event Serializer
class EventSerializer(serializers.ModelSerializer):
    """
    Serializer for Event model.
    Handles event details, scheduling, and pricing.
    """
    class Meta:
        model = Event
        fields = '__all__'

# Image Serializer
class ImageSerializer(serializers.ModelSerializer):
    """
    Serializer for Image model.
    Handles event image metadata and positioning.
    """
    class Meta:
        model = Image
        fields = '__all__'

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
