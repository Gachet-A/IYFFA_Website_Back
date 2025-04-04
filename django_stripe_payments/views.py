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
import stripe
import json
from .models import Payment
from .serializers import PaymentSerializer

print("Loading Stripe key:", settings.STRIPE_SECRET_KEY)
stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def create_payment_intent(request):
    print("Creating payment intent with key:", stripe.api_key)
    try:
        data = json.loads(request.body)
        print("Received data:", data)
        
        # Validate required fields
        required_fields = ['amount', 'email', 'name']
        for field in required_fields:
            if not data.get(field):
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validate amount
        amount = data.get('amount')
        if not isinstance(amount, (int, float)) or amount <= 0:
            return Response(
                {'error': 'Amount must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate currency (only CHF allowed)
        currency = 'chf'
        if data.get('currency', 'chf').lower() != 'chf':
            return Response(
                {'error': 'Only CHF currency is supported'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate email
        try:
            validate_email(data.get('email'))
        except ValidationError:
            return Response(
                {'error': 'Invalid email format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            payment_method_types=['card'],
            receipt_email=data.get('email'),
            metadata={
                'name': data.get('name'),
                'email': data.get('email')
            }
        )

        return Response({
            'clientSecret': intent.client_secret
        })

    except json.JSONDecodeError:
        return Response(
            {'error': 'Invalid JSON data'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [AllowAny]  # Default to AllowAny
    authentication_classes = []  # Disable authentication by default

    def get_permissions(self):
        """
        Override the default permission classes for specific actions.
        This method takes precedence over the REST_FRAMEWORK settings.
        """
        if self.action in ['create_payment_intent', 'webhook']:
            return [AllowAny()]
        return [IsAuthenticated()]  # Require authentication for other actions

    def get_authentication_classes(self):
        """
        Override the default authentication classes for specific actions.
        This method takes precedence over the REST_FRAMEWORK settings.
        """
        if self.action in ['create_payment_intent', 'webhook']:
            return []
        return super().get_authentication_classes()

    @csrf_exempt
    @require_POST
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], authentication_classes=[])
    def webhook(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            return HttpResponse(status=400)

        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            
            # Create payment record without user association
            Payment.objects.create(
                stripe_payment_id=payment_intent['id'],
                amount=payment_intent['amount'] / 100,  # Convert from cents to CHF
                currency='chf',  # Always CHF
                status='succeeded',
                email=payment_intent['receipt_email'],
                name=payment_intent['metadata'].get('name', '')
            )

        return HttpResponse(status=200) 