import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
import stripe
import json
from .models import Payment
from .serializers import PaymentSerializer
from django_rest.models import Cotisation
from django.utils import timezone
from datetime import timedelta

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Stripe with the secret key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY

def send_payment_confirmation_email(payment_data):
    """
    Sends a confirmation email for successful payments.
    Handles different email templates based on payment type.
    """
    try:
        subject = f"Thank you for your {payment_data['payment_type']}!"
        message = f"""
        Dear {payment_data['name']},

        Thank you for your {payment_data['payment_type']} of {payment_data['amount']} {payment_data['currency']}.

        Transaction ID: {payment_data['stripe_id']}

        If you have any questions, please contact us at {settings.DEFAULT_FROM_EMAIL}

        Best regards,
        IYFFA Team
        """

        if payment_data['payment_type'] == 'monthly_donation':
            message += f"""
            Your monthly donation of {payment_data['amount']} {payment_data['currency']} will be automatically processed each month.
            To manage or cancel your subscription, please contact us with your subscription ID: {payment_data['subscription_id']}
            """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [payment_data['email']],
            fail_silently=False,
        )
        logger.info(f"Confirmation email sent successfully to {payment_data['email']}")
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {str(e)}")

@api_view(['POST'])
@permission_classes([AllowAny])
def create_payment_intent(request):
    """
    Creates a payment intent for one-time donations or a subscription for monthly donations.
    Handles both authenticated and anonymous payments.
    """
    try:
        data = request.data
        amount = data.get('amount')
        email = data.get('email')
        name = data.get('name')
        payment_type = data.get('payment_type')

        if not all([amount, email, payment_type]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        if payment_type == 'membership_renewal' and not request.user.is_authenticated:
            return Response({'error': 'Authentication required for membership renewal'}, 
                          status=status.HTTP_401_UNAUTHORIZED)

        if payment_type == 'monthly_donation':
            # Create or retrieve customer
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'payment_type': payment_type,
                    'name': name
                }
            )

            # Create price for subscription
            price = stripe.Price.create(
                unit_amount=amount * 100,  # amount in cents
                currency='chf',
                recurring={'interval': 'month'},
                product_data={
                    'name': 'Monthly Donation',
                    'metadata': {
                        'payment_type': payment_type
                    }
                }
            )

            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': price.id}],
                metadata={
                    'payment_type': payment_type,
                    'name': name,
                    'email': email
                }
            )

            return Response({
                'subscriptionId': subscription.id,
                'clientSecret': subscription.latest_invoice.payment_intent.client_secret
            })

        else:
            # Create payment intent for one-time payment
            payment_intent = stripe.PaymentIntent.create(
                amount=amount * 100,  # amount in cents
                currency='chf',
                automatic_payment_methods={
                    'enabled': True,
                },
                metadata={
                    'payment_type': payment_type,
                    'name': name,
                    'email': email,
                    'user_id': str(request.user.id) if request.user.is_authenticated else 'anonymous'
                }
            )

            return Response({
                'clientSecret': payment_intent.client_secret
            })

    except Exception as e:
        logger.error(f"Error creating payment intent: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@require_POST
@permission_classes([AllowAny])
def webhook_handler(request):
    """
    Handles Stripe webhook events for payment processing.
    Processes both one-time payments and subscription payments.
    """
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
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            email = payment_intent.receipt_email or payment_intent.metadata.get('email')
            
            if not email:
                logger.warning("No email found in payment intent, skipping payment record creation")
                return HttpResponse(status=200)

            payment_data = {
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency,
                'stripe_id': payment_intent.id,
                'status': 'succeeded',
                'email': email,
                'name': payment_intent.metadata.get('name', 'Anonymous'),
                'payment_type': payment_intent.metadata.get('payment_type', 'one_time_donation'),
                'user_id': payment_intent.metadata.get('user_id')
            }

            payment = Payment.objects.create(**payment_data)
            send_payment_confirmation_email(payment_data)

        elif event.type == 'invoice.payment_succeeded':
            invoice = event.data.object
            customer = stripe.Customer.retrieve(invoice.customer)
            email = customer.email or invoice.metadata.get('email')
            
            if not email:
                logger.warning("No email found in invoice, skipping payment record creation")
                return HttpResponse(status=200)

            payment_data = {
                'amount': invoice.amount_paid / 100,
                'currency': invoice.currency,
                'stripe_id': invoice.payment_intent,
                'status': 'succeeded',
                'email': email,
                'name': customer.name or invoice.metadata.get('name', 'Anonymous'),
                'payment_type': 'monthly_donation',
                'subscription_id': invoice.subscription,
                'user_id': invoice.metadata.get('user_id')
            }

            payment = Payment.objects.create(**payment_data)
            send_payment_confirmation_email(payment_data)

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)

    return HttpResponse(status=200)

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment records.
    Requires authentication for listing and retrieving payments.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'webhook':
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_staff:
            return Payment.objects.all()
        return Payment.objects.filter(user_id=str(self.request.user.id)) 