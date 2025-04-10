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
        subject = f"Thank you for your Gift!"
        message = f"""
        Dear {payment_data['name']},

        Thank you for your gift of {payment_data['amount']} {payment_data['currency']} through {payment_data['payment_method']}

        """

        if payment_data['payment_type'] == 'monthly_donation':
            message += f"""
            Your monthly donation of {payment_data['amount']} {payment_data['currency']} will be automatically processed each month.
            
            To manage your subscription (including cancellation), click here: {payment_data['cancel_url']}
            """

        message += f"""
        If you have any questions, please contact us at {settings.DEFAULT_FROM_EMAIL}

        Best regards,
        IYFFA Team
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
    Creates a payment intent for one-time donations or a setup intent for monthly donations.
    Handles both authenticated and anonymous payments.
    """
    try:
        data = request.data
        amount = data.get('amount')
        email = data.get('email')
        name = data.get('name')
        payment_type = data.get('payment_type')
        payment_method_types = data.get('payment_method_types', ['card'])  # Get payment methods or default to card

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

            # Create setup intent for collecting payment method
            setup_intent = stripe.SetupIntent.create(
                customer=customer.id,
                payment_method_types=payment_method_types,  # Use the provided payment methods
                metadata={
                    'payment_type': payment_type,
                    'name': name,
                    'email': email,
                    'price_id': price.id,
                    'amount': amount
                }
            )

            return Response({
                'clientSecret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id
            })

        else:
            # Create payment intent for one-time payment
            payment_intent = stripe.PaymentIntent.create(
                amount=amount * 100,  # amount in cents
                currency='chf',
                payment_method_types=payment_method_types,  # Use the provided payment methods
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

@api_view(['POST'])
@permission_classes([AllowAny])
def create_monthly_subscription(request):
    """
    Creates a monthly subscription for recurring donations.
    Only supports card payments for subscriptions.
    """
    try:
        data = request.data
        amount = data.get('amount')
        email = data.get('email')
        name = data.get('name')
        address = data.get('address')
        payment_type = 'monthly_donation'  # Fixed for this endpoint

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

        # Create setup intent for collecting payment method
        # Only support card payments for subscriptions
        setup_intent = stripe.SetupIntent.create(
            customer=customer.id,
            payment_method_types=['card'],  # Only card for subscriptions
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

@csrf_exempt
@require_POST
@permission_classes([AllowAny])
@authentication_classes([])  # Explicitly disable authentication
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
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            
            # Create payment record with valid fields
            Payment.objects.create(
                stripe_payment_id=setup_intent.id,
                amount=int(float(setup_intent.metadata.get('amount', 0)) * 100),  # Convert to cents
                currency='chf',
                status='succeeded',
                payment_type='monthly_donation',
                email=setup_intent.metadata.get('email'),
                payment_method='card',  # Since we only allow card for subscriptions
                subscription_id=subscription.id  # Store the subscription ID
            )
            
            # Get the direct cancellation URL (frontend route)
            cancel_url = f"http://localhost:8080/cancel-subscription/{subscription.id}"
            
            # Send confirmation email with cancel_url
            send_payment_confirmation_email({
                'email': setup_intent.metadata.get('email'),
                'name': setup_intent.metadata.get('name'),
                'amount': setup_intent.metadata.get('amount'),
                'payment_type': 'monthly_donation',
                'cancel_url': cancel_url,
                'currency': 'chf',  # Add currency
                'payment_method': 'card'  # Add payment method
            })
            
            return HttpResponse(status=200)

        elif event.type == 'invoice.payment_succeeded':
            invoice = event.data.object
            subscription = invoice.subscription
            
            # Update payment status if it exists
            payment = Payment.objects.filter(subscription_id=subscription).first()
            if payment:
                payment.status = 'active'
                payment.save()
                
                # Send confirmation email for successful payment
                send_payment_confirmation_email({
                    'email': payment.email,
                    'amount': payment.amount / 100,  # Convert back to CHF
                    'payment_type': payment.payment_type,
                    'currency': payment.currency,
                    'payment_method': payment.payment_method,
                    'name': setup_intent.metadata.get('name', 'Donor')  # Get name from setup intent metadata
                })
            
            return HttpResponse(status=200)

        elif event.type == 'customer.subscription.updated':
            subscription = event.data.object
            payment = Payment.objects.filter(subscription_id=subscription.id).first()
            if payment:
                payment.status = subscription.status
                payment.save()
            
            return HttpResponse(status=200)

        elif event.type == 'customer.subscription.deleted':
            subscription = event.data.object
            payment = Payment.objects.filter(subscription_id=subscription.id).first()
            if payment:
                payment.status = 'canceled'
                payment.save()
            
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

            payment_data = {
                'stripe_payment_id': payment_intent.id,
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency,
                'status': 'succeeded',
                'email': email,
                'payment_type': payment_intent.metadata.get('payment_type', 'one_time_donation'),
                'payment_method': payment_method_type
            }

            payment = Payment.objects.create(**payment_data)
            send_payment_confirmation_email({
                'stripe_id': payment_intent.id,
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency,
                'email': email,
                'name': payment_intent.metadata.get('name', 'Anonymous'),
                'payment_type': payment_intent.metadata.get('payment_type', 'one_time_donation'),
                'payment_method': payment_method_type
            })

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)

    return HttpResponse(status=200)

@api_view(['POST'])
@permission_classes([AllowAny])
def cancel_subscription(request, subscription_id):
    """
    Cancels a subscription and updates the payment record.
    """
    try:
        # Cancel the subscription in Stripe
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        # Update the payment record
        payment = Payment.objects.filter(subscription_id=subscription_id).first()
        if payment:
            payment.status = 'canceled'
            payment.save()
        
        return Response({
            'status': 'success',
            'message': 'Subscription will be canceled at the end of the current period'
        })
        
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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