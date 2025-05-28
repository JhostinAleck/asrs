
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import logging

security_logger = logging.getLogger('security')

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with security logging"""
    
    def validate(self, attrs):
        # Get request info for logging
        request = self.context.get('request')
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        try:
            data = super().validate(attrs)
            
            # Log successful login
            security_logger.info(
                f"Successful login - User: {self.user.username}, IP: {ip_address}, UA: {user_agent}"
            )
            
            # Track login attempt
            from .models import LoginAttempt
            LoginAttempt.objects.create(
                username=self.user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            )
            
            return data
            
        except Exception as e:
            # Log failed login
            username = attrs.get('username', 'unknown')
            security_logger.warning(
                f"Failed login attempt - User: {username}, IP: {ip_address}, UA: {user_agent}, Error: {str(e)}"
            )
            
            # Track failed login attempt
            from .models import LoginAttempt
            LoginAttempt.objects.create(
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            
            raise
    
    def get_client_ip(self, request):
        """Get client IP considering reverse proxy"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
