from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager

# File that defines the database classes

# Custom UserManager for email-based authentication
class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        # Utiliser l'email comme username par défaut
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)
        
        # Créer l'utilisateur
        user = self.model(
            email=email,
            username=email,  # Forcer le username à être l'email
            **extra_fields
        )
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        return self.create_user(email, password, **extra_fields)

# User model
class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Uses email as the unique identifier for authentication.
    """
    USER_TYPE_CHOICES = (
        ('admin', 'Administrator'),  # Full access to all features
        ('user', 'Regular User'),    # Standard user access
    )
    
    # Custom fields
    birthdate = models.DateField(null=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=45, null=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='user')
    status = models.BooleanField(default=True)
    cgu = models.BooleanField(default=False)    # Terms of service acceptance
    stripe_id = models.CharField(max_length=100, blank=True, null=True)
    otp_enabled = models.BooleanField(default=False)
    otp_secret = models.CharField(max_length=16, blank=True, null=True)  # For storing temporary OTP codes
    
    # Rendre le username unique mais optionnel
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        help_text='Username field, will be set to email by default.',
    )
    
    # Set custom manager
    objects = CustomUserManager()
    
    # Authentication settings
    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'birthdate', 'phone_number']

    class Meta:
        db_table = 'ifa_user'

    def save(self, *args, **kwargs):
        # S'assurer que le username est toujours égal à l'email
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def is_admin(self):
        """Check if user has admin privileges"""
        return self.user_type == 'admin'

    def disable_2fa(self):
        """Disable two-factor authentication for the user"""
        self.otp_enabled = False
        self.otp_secret = None
        self.save()

# Article model
class Article(models.Model):
    """
    Article model for managing blog posts or news articles.
    Each article is associated with a user and has basic content fields.
    """
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    text = models.TextField()
    creation_time = models.DateTimeField(auto_now_add=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")

    class Meta:
        db_table = 'ifa_article'

    def __str__(self):
        return self.title

# Project model
class Project(models.Model):
    """
    Project model for managing user projects.
    Includes budget tracking and project details.
    """
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=45)
    description = models.TextField()
    budget = models.FloatField()
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")

    class Meta:
        db_table = 'ifa_project'

    def __str__(self):
        return self.title

# Document model
class Document(models.Model):
    """
    Document model for storing project-related files.
    Links documents to specific projects.
    """
    id = models.AutoField(primary_key=True)
    url = models.CharField(max_length=255)
    user_id = models.ForeignKey(Project, on_delete=models.CASCADE, db_column="project_id")

    class Meta:
        db_table = 'ifa_document'

# Event model
class Event(models.Model):
    """
    Event model for managing organization events.
    Includes event details, location, and pricing information.
    """
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=45)
    description = models.TextField()
    start_datetime = models.DateTimeField()  # Required field for start date and time
    end_datetime = models.DateTimeField(null=True, blank=True)  # Optional field for end date and time
    location = models.CharField(max_length=255)
    price = models.FloatField()
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")

    class Meta:
        db_table = 'ifa_event'

    def __str__(self):
        return self.title

# Image model
class Image(models.Model):
    id = models.AutoField(primary_key=True)
    file = models.ImageField(upload_to='media/', max_length=255)
    position = models.IntegerField(default=0)
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    event_id = models.ForeignKey(Event, on_delete=models.CASCADE, db_column="event_id", related_name='images')

    class Meta:
        db_table = 'ifa_image'
        ordering = ['position']

    def __str__(self):
        return f"Image {self.id} for {self.event_id.title}"

    def delete(self, *args, **kwargs):
        # Delete the actual file when the model instance is deleted
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)

# Cotisation model 
class Cotisation(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    type = models.CharField(max_length=45)
    amount = models.FloatField()
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")

    class Meta:
        db_table = 'ifa_cotisation' # Define table name

# Payment table
class Payment(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    creation_time = models.DateTimeField(auto_now_add=True)  # Timestamp
    amount = models.FloatField()
    stripe_id = models.BigIntegerField()
    status = models.CharField(max_length=45)
    currency = models.CharField(max_length=45)
    event_id = models.ForeignKey(Event, on_delete=models.CASCADE, db_column="event_id")
    cot_id = models.ForeignKey(Cotisation, on_delete=models.CASCADE, db_column="cotisation_id")

    class Meta:
        db_table = 'ifa_payment'