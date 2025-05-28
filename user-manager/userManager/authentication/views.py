from django.shortcuts import render

# Create your views here.

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse
import logging
import jwt
from django.conf import settings

logger = logging.getLogger('authentication')
security_logger = logging.getLogger('security')
User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom login view with enhanced security"""
    
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        # Rate limiting check
        ip_address = self.get_client_ip(request)
        cache_key = f"login_attempts_{ip_address}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            security_logger.error(f"Rate limit exceeded for IP: {ip_address}")
            return Response({
                'error': 'Too many login attempts. Please try again later.',
                'retry_after': 300
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        response = super().post(request, *args, **kwargs)
        
        if response.status_code != 200:
            # Increment failed attempts
            cache.set(cache_key, attempts + 1, 300)  # 5 minutes
            
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

@api_view(['POST'])
@permission_classes([AllowAny])
def validate_token(request):
    """Validate JWT token - called by Nginx"""
    
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.warning("Missing or invalid authorization header")
        return JsonResponse({'valid': False, 'error': 'Missing token'}, status=401)
    
    token = auth_header.split(' ')[1]
    
    try:
        # Validate token
        UntypedToken(token)
        
        # Decode to get user info
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = decoded_token['user_id']
        
        try:
            user = User.objects.get(id=user_id)
            logger.info(f"Token validated successfully for user: {user.username}")
            
            response = JsonResponse({
                'valid': True,
                'user_id': user.id,
                'username': user.username
            })
            response['X-User'] = user.username
            return response
            
        except User.DoesNotExist:
            logger.warning(f"Token valid but user not found: {user_id}")
            return JsonResponse({'valid': False, 'error': 'User not found'}, status=401)
            
    except TokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return JsonResponse({'valid': False, 'error': 'Invalid token'}, status=401)
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return JsonResponse({'valid': False, 'error': 'Validation error'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get user profile information"""
    
    logger.info(f"Profile requested by user: {request.user.username}")
    
    return Response({
        'username': request.user.username,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'is_staff': request.user.is_staff,
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'user_manager',
        'timestamp': timezone.now(),
        'version': '1.0.0'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_stats(request):
    """Security statistics endpoint"""
    
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)
    
    from .models import LoginAttempt
    from datetime import timedelta
    
    now = timezone.now()
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(days=1)
    
    stats = {
        'total_attempts_last_hour': LoginAttempt.objects.filter(timestamp__gte=last_hour).count(),
        'failed_attempts_last_hour': LoginAttempt.objects.filter(timestamp__gte=last_hour, success=False).count(),
        'total_attempts_last_day': LoginAttempt.objects.filter(timestamp__gte=last_day).count(),
        'failed_attempts_last_day': LoginAttempt.objects.filter(timestamp__gte=last_day, success=False).count(),
        'unique_ips_last_day': LoginAttempt.objects.filter(timestamp__gte=last_day).values('ip_address').distinct().count(),
    }
    
    return Response(stats)
