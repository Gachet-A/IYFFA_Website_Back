from django.db import models

class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ('one_time_donation', 'One Time Donation'),
        ('monthly_donation', 'Monthly Donation'),
        ('membership_renewal', 'Membership Renewal'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('card', 'Credit Card'),
        ('twint', 'TWINT'),
        ('paypal', 'PayPal'),
    )

    stripe_payment_id = models.CharField(max_length=100, unique=True)
    amount = models.IntegerField()
    currency = models.CharField(max_length=3, default='chf')
    status = models.CharField(max_length=20)
    email = models.EmailField()
    payment_type = models.CharField(
        max_length=20, 
        choices=PAYMENT_TYPE_CHOICES, 
        default='one_time_donation'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True
    )
    cotisation = models.ForeignKey(
        'django_rest.Cotisation', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='stripe_payments'
    )  # Optional, only for membership renewals
    subscription_id = models.CharField(max_length=100, null=True, blank=True)  # For monthly donations
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} - {self.amount} {self.currency} ({self.status})" 