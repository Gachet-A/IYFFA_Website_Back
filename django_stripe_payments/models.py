from django.db import models

class Payment(models.Model):
    stripe_payment_id = models.CharField(max_length=100, unique=True)
    amount = models.IntegerField()
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20)
    email = models.EmailField()
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.amount} {self.currency} ({self.status})" 