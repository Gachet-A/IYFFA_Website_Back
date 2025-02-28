from django.db import models

# File that defines the database classes

# User model
class User(models.Model):
    usr_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    usr_name = models.CharField(max_length=45)
    usr_surname = models.CharField(max_length=45)
    usr_birthdate = models.DateField()
    usr_email = models.CharField(max_length=45)
    usr_phone_number = models.CharField(max_length=45)  # VARCHAR(45) to include country index
    usr_status = models.BooleanField()
    usr_cgu = models.BooleanField()
    usr_type = models.CharField(max_length=45)
    usr_stripe_id = models.BigIntegerField()

    class Meta:
        db_table = 'ifa_user' # Define table name

    def __str__(self):
        return self.usr_name # String representation
    
# Article model
class Article(models.Model):
    art_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    art_title = models.CharField(max_length=255)  # VARCHAR(255)
    art_text = models.TextField()
    art_creation_time = models.DateTimeField(auto_now_add=True)  # Timestamp
    art_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")  # Foreign Key to ifa_user

    class Meta:
        db_table = 'ifa_article'  # Define table name

    def __str__(self):
        return self.art_title  # String representation
    
# Project model
class Project(models.Model):
    pro_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    pro_title = models.CharField(max_length=45)
    pro_description = models.TextField()
    pro_budget = models.FloatField()
    pro_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")  # Foreign Key to ifa_user

    class Meta:
        db_table = 'ifa_project' # Define table name

    def __str__(self):
        return self.pro_title  # String representation
    
# Document model
class Document(models.Model):
    doc_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    doc_url = models.CharField(max_length=255)
    pro_user_id = models.ForeignKey(Project, on_delete=models.CASCADE, db_column="pro_id")  # Foreign Key to ifa_project

    class Meta:
        db_table = 'ifa_document' # Define table name
    
# Event model
class Event(models.Model):
    eve_id = models.AutoField(primary_key=True)  # Auto-incrementing PK
    eve_title = models.CharField(max_length=45)
    eve_description = models.TextField()
    eve_date = models.DateField()
    eve_location = models.CharField(max_length=255)
    eve_price = models.FloatField()
    eve_user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="usr_id")  # Foreign Key to ifa_user

    class Meta:
        db_table = 'ifa_event' # Define table name

    def __str__(self):
        return self.eve_title # String representation
    
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