from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager

# File that defines the database classes

# Custom UserManager for email-based authentication
class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        extra_fields.setdefault('username', email)
        user = self.model(
            email=email,
            **extra_fields
        )
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
    phone_number = models.CharField(max_length=45, null=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='user')
    status = models.BooleanField(default=True)
    cgu = models.BooleanField(default=False)    # Terms of service acceptance
    stripe_id = models.CharField(max_length=100, blank=True, null=True)
    otp_enabled = models.BooleanField(default=False)
    otp_secret = models.CharField(max_length=16, blank=True, null=True)  # For storing temporary OTP codes
    
    # Override email field to make it unique
    email = models.EmailField(unique=True)
    
    # Set custom manager
    objects = CustomUserManager()
    
    # Authentication settings
    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'birthdate', 'phone_number']

    class Meta:
        db_table = 'ifa_user'

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
    art_id = models.AutoField(primary_key=True)
    art_title = models.CharField(max_length=255)
    art_text = models.TextField()
    art_creation_time = models.DateTimeField(auto_now_add=True)
    art_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")

    class Meta:
        db_table = 'ifa_article'

    def __str__(self):
        return self.art_title

# Project model
class Project(models.Model):
    """
    Project model for managing user projects.
    Includes budget tracking and project details.
    """
    pro_id = models.AutoField(primary_key=True)
    pro_title = models.CharField(max_length=45)
    pro_description = models.TextField()
    pro_budget = models.FloatField()
    pro_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")

    class Meta:
        db_table = 'ifa_project'

    def __str__(self):
        return self.pro_title

# Document model
class Document(models.Model):
    """
    Document model for storing project-related files.
    Links documents to specific projects.
    """
    doc_id = models.AutoField(primary_key=True)
    doc_url = models.CharField(max_length=255)
    pro_user_id = models.ForeignKey(Project, on_delete=models.CASCADE, db_column="pro_id")

    class Meta:
        db_table = 'ifa_document'

# Event model
class Event(models.Model):
    """
    Event model for managing organization events.
    Includes event details, location, and pricing information.
    """
    eve_id = models.AutoField(primary_key=True)
    eve_title = models.CharField(max_length=45)
    eve_description = models.TextField()
    eve_date = models.DateField()
    eve_location = models.CharField(max_length=255)
    eve_price = models.FloatField()
    eve_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")

    class Meta:
        db_table = 'ifa_event'

    def __str__(self):
        return self.eve_title

# Image model
class Image(models.Model):
    img_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    img_url = models.CharField(max_length=255)
    img_position = models.IntegerField(10)
    img_event_id = models.ForeignKey(Event, on_delete=models.CASCADE, db_column="eve_id")  # Foreign Key to ifa_event

    class Meta:
        db_table = 'ifa_image' # Define table name

# Cotisation model 
class Cotisation(models.Model):
    cot_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    cot_type = models.CharField(max_length=45)
    cot_amount = models.FloatField()
    cot_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")  # Foreign Key to ifa_user

    class Meta:
        db_table = 'ifa_cotisation' # Define table name

# Payment table
class Payment(models.Model):
    pay_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    pay_creation_time = models.DateTimeField(auto_now_add=True)  # Timestamp
    pay_amount = models.FloatField()
    pay_stripe_id = models.BigIntegerField()
    pay_status = models.CharField(max_length=45)
    pay_currency = models.CharField(max_length=45)
    pay_event_id = models.ForeignKey(Event, on_delete=models.CASCADE, db_column="eve_id")  # Foreign Key to ifa_event
    pay_cot_id = models.ForeignKey(Cotisation, on_delete=models.CASCADE, db_column="cot_id")  # Foreign Key to ifa_cotisation

    class Meta:
        db_table = 'ifa_payment'